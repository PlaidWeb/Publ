# utils.py
""" Some useful utilities that don't belong anywhere else """

import ast
import functools
import html
import html.parser
import logging
import os
import re
import typing
import urllib.parse
from typing import Optional

import arrow
import flask
import slugify
import werkzeug.routing

from . import model
from .config import config

LOGGER = logging.getLogger(__name__)

T = typing.TypeVar('T')  # pylint:disable=invalid-name
ArgDict = typing.Dict[str, typing.Any]
ListLike = typing.Union[typing.List[T],
                        typing.Tuple[T, ...],
                        typing.Set[T]]
TagAttr = typing.Union[str, bool, None]
TagAttrs = typing.Dict[str, TagAttr]

_TagKey = slugify.Slugify(to_lower=True)  # type:ignore


class CallableProxy:
    """ Wrapper class to make args possible on properties. """
    # pylint: disable=too-few-public-methods

    def __init__(self, func: typing.Callable[..., T]):
        """ Construct the property proxy.

        :param func: The function to wrap
        """

        self._func: typing.Callable[..., T] = func

    @functools.lru_cache()
    def _cached_default(self, *_):
        """ caching wrapper to memoize call against everything that might affect it """
        return self._func()

    def _default(self):
        from . import user  # pylint:disable=cyclic-import
        return self._cached_default(flask.request.url, user.get_active())

    def __call__(self, *args, **kwargs):
        # use the new kwargs to override the defaults
        return self._func(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._default(), name)

    def __bool__(self) -> bool:
        return bool(self._default())

    def __len__(self) -> int:
        return len(self._default())

    def __str__(self) -> str:
        return str(self._default())

    def __iter__(self):
        return self._default().__iter__()

    def __getitem__(self, key):
        return self._default().__getitem__(key)

    def __hash__(self):
        return hash((CallableProxy, self._func))

    def __eq__(self, other):
        return self._default() == other

    def __contains__(self, item):
        return item in self._default()

    def __add__(self, other):
        return self._default() + other


class TrueCallableProxy(CallableProxy):
    """ A version of CallableProxy that is always truthy """
    # pylint: disable=too-few-public-methods

    def __bool__(self):
        return True


class CallableValue(CallableProxy):
    """ A version of CallableProxy that returns a fixed value """
    # pylint:disable=too-few-public-methods

    def __init__(self, value):
        super().__init__(lambda *args, **kwargs: value)


#: arrow format string for 'day' archives
DAY_FORMAT = 'YYYY-MM-DD'

#: arrow format string for 'month' archives
MONTH_FORMAT = 'YYYY-MM'

#: arrow format string for 'year' archives
YEAR_FORMAT = 'YYYY'

#: arrow format string for 'week' archives
WEEK_FORMAT = 'YYYYMMDD_w'


def parse_date(datestr: str) -> typing.Tuple[arrow.Arrow, str, str]:
    """ Parse a date expression into a tuple of:
    ``(start_date, span_type, span_format)``

    :param str datestr: A date specification, in the format of YYYY-MM-DD (dashes optional)
    """

    match = re.match(
        r'([0-9]{4})(-?([0-9]{1,2}))?(-?([0-9]{1,2}))?(_w)?$', datestr)
    if not match:
        return (arrow.get(datestr,
                          tzinfo=config.timezone).replace(tzinfo=config.timezone),
                'day', DAY_FORMAT)

    year, month, day, week = match.group(1, 3, 5, 6)
    start = arrow.Arrow(year=int(year), month=int(
        month or 1), day=int(day or 1), tzinfo=config.timezone)

    if week:
        return start.span('week')[0], 'week', WEEK_FORMAT

    if day:
        return start, 'day', DAY_FORMAT

    if month:
        return start, 'month', MONTH_FORMAT

    return start, 'year', YEAR_FORMAT


def find_file(path: str, search_path: typing.Union[str, ListLike[str]]) -> typing.Optional[str]:
    """ Find a file by relative path. Arguments:

    :param str path: the image's filename
    :param list search_path: a list of directories to check in

    :returns: the resolved file path
    """

    for relative in as_list(search_path):
        candidate = os.path.normpath(os.path.join(relative, path))
        if os.path.isfile(candidate):
            return candidate

    return None


def static_url(path: str, absolute: bool = False) -> str:
    """ Shorthand for returning a URL for the requested static file.

    Arguments:

    :param str path: the path to the file (relative to the static files directory)
    :param bool absolute: whether the link should be absolute or relative
    """

    if os.sep != '/':
        path = '/'.join(path.split(os.sep))

    return flask.url_for('static', filename=path, _external=absolute)


def make_tag(name: str,
             attrs: TagAttrs,
             start_end: bool = False) -> str:
    """ Build an HTML tag from the given name and attributes.

    :param str name: the name of the tag (p, div, etc.)
    :param attrs: a dict or list of attributes to apply to the tag
    :param bool start_end: whether this tag should be self-closing

    If an attribute's value is None it will be written as a standalone attribute,
    e.g. ``<audio controls>``. To suppress it entirely, make the value explicitly False.
    """

    text = '<' + name

    if isinstance(attrs, dict):
        attr_list = attrs.items()
    elif isinstance(attrs, list):
        attr_list = attrs
    elif attrs is not None:
        raise TypeError("Unhandled attrs type " + str(type(attrs)))

    for key, val in attr_list:
        if val is not False:
            text += f' {key}'
            if val is not None:
                import markupsafe
                escaped = html.escape(str(val), False).replace('"', '&#34;')

                if isinstance(val, CallableProxy):
                    val = val()
                if isinstance(val, markupsafe.Markup):
                    # We just double-escaped all entities...
                    escaped = re.sub(r'&amp;([a-zA-Z0-9.\-_\:]+;)', r'&\1', val)
                text += f'="{escaped}"'
    if start_end:
        text += ' /' if attrs else '/'
    text += '>'
    return text


def file_fingerprint(fullpath: str) -> str:
    """ Get a metadata fingerprint for a file """
    try:
        stat = os.stat(fullpath)
        return ','.join([str(value)
                         for value in [stat.st_ino, stat.st_mtime, stat.st_size]
                         if value])
    except FileNotFoundError:
        LOGGER.warning("Attempted to get fingerprint of nonexistent file %s", fullpath)
        return ''


def remap_args(input_args: typing.Dict[str, typing.Any],
               remap: typing.Dict[str, typing.Union[str, ListLike[str]]]
               ) -> typing.Dict[str, typing.Any]:
    """ Generate a new argument list by remapping keys.

    :param dict input_args: The input argument list
    :param dict remap: A mapping of destination key -> priority list of source keys
    """
    out_args = input_args
    for dest_key, src_keys in remap.items():
        remap_value = None

        for key in as_list(src_keys):
            if key in input_args:
                remap_value = input_args[key]
                break

        if remap_value is not None:
            if out_args is input_args:
                out_args = {**input_args}
            out_args[dest_key] = remap_value

    return out_args


def remap_link_target(path: str, absolute: bool = False) -> str:
    """ Remap a link target from a path, URL, or static file reference.

    :param str path: The original link target; start with ``@`` to indicate a
        static file

    :param bool absolute: Whether to make the link absolute with respect to the
        current page URL
    """
    if path.startswith('@'):
        # static resource
        return static_url(path[1:], absolute=absolute)

    if absolute:
        # absolute-ify whatever the URL is
        return urllib.parse.urljoin(flask.request.url, path)

    return path


def get_category(filename: str) -> str:
    """ Get a default category name from a filename in a cross-platform manner """
    return '/'.join(os.path.dirname(filename).split(os.sep))


class HTMLTransform(html.parser.HTMLParser):
    """ Wrapper to HTMLParser to make it easier to build a SAX-style processor.

    You will probably want to implement:

    * ``handle_starttag(self, tag, attrs)``
    * ``handle_endtag(self, tag)``
    * ``handle_data(self, data)``
    * ``handle_startendtag(self, tag, attrs)``
    """

    def __init__(self):
        super().__init__()

        self.reset()
        self.strict = False
        self.convert_charrefs = False
        self._fed = []

    def feed(self, data: str):
        """ Feed in some text data.

        Overrides the base class to ensure that it's handled like a plain string
        and not a MarkupSafe string (which causes double-escaping to happen)
        """
        super().feed(str(data))

    def append(self, item: str):
        """ Append some text to the output """
        self._fed.append(item)

    def get_data(self) -> str:
        """ Concatenate the output """
        return ''.join(self._fed)

    def handle_entityref(self, name: str):
        self.handle_data('&' + name + ';')

    def handle_charref(self, name: str):
        self.handle_data('&#' + name + ';')

    def error(self, message: str):
        """ Deprecated, per https://bugs.python.org/issue31844 """


def prefix_normalize(kwargs: ArgDict) -> ArgDict:
    """

    Given an argument list where one of them is ``prefix``, normalize the
    arguments to convert ``{prefix}{key}`` to ``{key}`` and remove the prefixed
    versions

    For example::

        {
            'prefix': 'index_',
            'width': 320,
            'index_width': 256,
        }

    becomes::

        {
            'width': 256
        }

    """

    prefixed = {}
    removed = []
    if 'prefix' in kwargs:
        for prefix in as_list(kwargs.get('prefix')):
            for k, val in kwargs.items():
                if k.startswith(prefix):
                    prefixed[k[len(prefix):]] = val
                    removed.append(k)

    normalized = {**kwargs, **prefixed}
    for k in removed:
        normalized.pop(k, None)
    return normalized


def is_list(item: typing.Any) -> bool:
    """ Return if this is a list-type thing """
    return bool(getattr(item, '__iter__', None)) and not isinstance(item, str)


def as_list(item: typing.Any) -> ListLike:
    """ Return list-type things directly; convert other things into a tuple """
    if item is None:
        return ()

    if is_list(item):
        return item

    return (item,)


class CategoryConverter(werkzeug.routing.PathConverter):
    """ A version of PathConverter that only accepts valid Publ categories
    (i.e. no segment starts with _) """

    def to_python(self, value: str) -> str:
        for part in value.split('/'):
            if part[0] == '_':
                raise werkzeug.routing.ValidationError
        return super().to_python(value)


class TemplateConverter(werkzeug.routing.UnicodeConverter):
    """ A version of UnicodeConverter that doesn't accept strings beginning with _ """

    def to_python(self, value: str) -> str:
        if value[0] == '_':
            raise werkzeug.routing.ValidationError
        return super().to_python(value)


def redir_path(path: typing.Optional[str] = None) -> str:
    """ Convert a URI path to a path fragment, suitable for url_for

    :param str path: The path to redirect to; uses the current request.full_path
        if unspecified

    """

    if path is None:
        path = flask.request.full_path
    else:
        path = str(path)

    # strip off leading slashes
    path = re.sub(r'^/*', r'', path)
    # if there's a trailing ? strip that off too
    path = re.sub(r'\?$', r'', path)

    return path


def secure_link(endpoint: str, *args, **kwargs) -> str:
    """ :py:func:`flask.url`_for except it will force the link to be secure if
    we are configured with ``AUTH_FORCE_HTTPS`` """
    force_ssl = config.auth.get('AUTH_FORCE_HTTPS')

    if force_ssl and flask.request.scheme != 'https':
        kwargs = {**kwargs,
                  '_external': True,
                  '_scheme': 'https'}
    return flask.url_for(endpoint, *args, **kwargs)


def auth_link(endpoint: str, auto_redir=True) -> typing.Callable[..., str]:
    """ Generates a function that maps an optional redir parameter to the
    specified endpoint. If redir is unspecified it defaults to the current
    request's full_path. """
    def endpoint_link(redir=None, absolute=False, **kwargs):
        LOGGER.debug("Getting %s for redir=%s kwargs=%s", endpoint, redir, kwargs)
        redir = redir_path(redir) if redir or auto_redir else None

        return secure_link(endpoint, redir=redir, _external=absolute, **kwargs)

    return CallableProxy(endpoint_link)


def stash(func: typing.Optional[typing.Callable] = None):
    """ Decorator to memoize a function onto the request's global context.
    """

    def make_hashable(item):
        from . import caching
        if isinstance(item, (str, caching.Memoizable)):
            return item
        if isinstance(item, (list, tuple)):
            return tuple(make_hashable(i) for i in item)
        if isinstance(item, set):
            return frozenset(make_hashable(i) for i in item)
        if isinstance(item, dict):
            return frozenset((make_hashable(k), make_hashable(v)) for k, v in item.items())
        return item

    def decorator(inner: typing.Callable):
        def wrapped_func(*args, **kwargs):
            if 'store' not in flask.g:
                flask.g.store = {}  # pylint:disable=assigning-non-slot
            if inner not in flask.g.store:
                flask.g.store[inner] = {}
            store = flask.g.store[inner]

            cache_key = (make_hashable(args), make_hashable(kwargs))
            if cache_key in store:
                return store[cache_key]

            val = inner(*args, **kwargs)
            store[cache_key] = val
            return val
        return wrapped_func

    return decorator(func) if func else decorator


def parse_tuple_string(argument: typing.Union[str, typing.Tuple, typing.List],
                       type_func=int) -> typing.Optional[typing.Tuple]:
    """ Return a tuple from parsing 'a,b,c,d' -> (a,b,c,d) """
    if argument is None:
        return None
    if isinstance(argument, str):
        return tuple(type_func(p.strip()) for p in argument.split(','))
    return tuple(argument)


@functools.lru_cache()
def tag_key(tag):
    """ Given a tag, return its normalized key """
    if isinstance(tag, str):
        return _TagKey(tag)
    if isinstance(tag, model.EntryTag):
        return tag.key
    if isinstance(tag, model.EntryTagged):
        return tag.tag.key
    raise ValueError(f"TagSet got non-tag-type {type(tag)}")


def tag_cname(tag) -> str:
    """ Get the canonical name of a tag from a name or key """
    record = model.EntryTag.get(key=tag_key(tag))
    if record:
        return record.name
    return tag


class TagSet(typing.Set[str]):
    """ A frozenset-equivalent class that is case-insensitive """

    def __init__(self, contents: typing.Optional[ListLike[str]] = None):
        super().__init__()
        if contents:
            storage = {tag_key(v): tag_cname(v) for v in contents}
            self._keys = frozenset(storage.keys())
            self._values = frozenset(storage.values())
        else:
            self._keys = frozenset()
            self._values = frozenset()

    def __contains__(self, key) -> bool:
        return tag_key(key) in self._keys

    def __iter__(self):
        return self._values.__iter__()

    def __hash__(self):
        return hash(self._keys)

    def __repr__(self):
        return f'{self.__class__}({set(self._values)})'

    def __str__(self):
        return str(set(self._values))

    def __or__(self, other):
        return TagSet(list(self) + list(other))

    @staticmethod
    def _fold(items):
        return {tag_key(k) for k in items}

    def __and__(self, other):
        folded = self._fold(other)
        return TagSet((k for k in self if tag_key(k) in folded))

    def __xor__(self, other):
        folded = self._fold(self) ^ self._fold(other)
        return TagSet((k for k in self | other if tag_key(k) in folded))

    def __sub__(self, other):
        folded = self._fold(other)
        return TagSet((k for k in self if tag_key(k) not in folded))

    def __len__(self):
        return len(self._values)

    def __bool__(self):
        return bool(self._values)

    def __eq__(self, other):
        folded = self._fold(other)
        return self._keys == folded

    def __ne__(self, other):
        folded = self._fold(other)
        return self._keys != folded

    def __le__(self, other):
        return self._fold(self) <= self._fold(other)

    def __lt__(self, other):
        return self._fold(self) < self._fold(other)

    def keys(self):
        """ Return the case-folded names """
        return self._keys

    def values(self):
        """ return the case-preserved names """
        return self._values


def strip_single_paragraph(text: str):
    """ If the provided HTML text has only a single paragraph, strip it off. """

    stripped = re.sub(r'^<p>(.*)</p>$', r'\1', text.strip())
    if '<p>' in stripped:
        return text
    return stripped


def parse_spec(text: str, pos_limit: Optional[int] = None) -> typing.Tuple[str, list, ArgDict]:
    """ Given a string like ``foo{10,bar=baz}``, parse out the argument lists.

    :param str text: The text to parse
    :param int pos_limit: The maximum number of positional args to allow
    :returns: Tuple of text, pos_args, kw_args
    """
    match = re.match(r'([^\{]*)(\{(.*)\})$', text)
    if match:
        pos_args, kw_args = parse_arglist(match.group(3), pos_limit)
        return match.group(1), pos_args, kw_args

    return text, [], {}


def parse_arglist(args: str, pos_limit: Optional[int] = None) -> typing.Tuple[list, ArgDict]:
    """ Parse an argument list into pos_args, kw_args"""
    tree = ast.parse(f'f({args})')
    expr = typing.cast(ast.Expr, tree.body[0])
    funccall = typing.cast(ast.Call, expr.value)

    pos_args = [ast.literal_eval(arg) for arg in funccall.args]
    if pos_limit is not None and len(pos_args) > pos_limit:
        raise TypeError(
            f"Expected at most {pos_limit} positional args but {len(pos_args)} were given")

    kwargs = {arg.arg: ast.literal_eval(arg.value)
              for arg in funccall.keywords if arg.arg}

    LOGGER.debug("pos_args=%s kw_args=%s", pos_args, kwargs)
    return pos_args, kwargs


def canonicize_url(url: str) -> str:
    """ Canonicize a URL to make them string-comparable """
    assert url is not None

    parsed = urllib.parse.urlparse(url)._asdict()
    parsed['netloc'] = parsed['netloc'].casefold()
    if not parsed.get('path'):
        parsed['path'] = '/'
    return urllib.parse.urlunparse(urllib.parse.ParseResult(**parsed))
