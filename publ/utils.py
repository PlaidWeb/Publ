# utils.py
""" Some useful utilities that don't belong anywhere else """

import html
import html.parser
import logging
import os
import re
import urllib.parse

import arrow
import flask
import slugify
import werkzeug.routing

from . import config, model

LOGGER = logging.getLogger(__name__)


class CallableProxy:
    """ Wrapper class to make args possible on properties. """
    # pylint: disable=too-few-public-methods

    def __init__(self, func):
        """ Construct the property proxy.

        func -- The function to wrap
        """

        self._func = func if func else (lambda *args, **kwargs: '')

    def __call__(self, *args, **kwargs):
        # use the new kwargs to override the defaults
        return self._func(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self(), name)

    def __bool__(self):
        return bool(self())

    def __len__(self):
        return 1 if self() else 0

    def __str__(self):
        return str(self())

    def __iter__(self):
        return self().__iter__()

    def __getitem__(self, key):
        return self().__getitem__(key)


class TrueCallableProxy(CallableProxy):
    """ A version of CallableProxy that is always truthy """
    # pylint: disable=too-few-public-methods

    def __bool__(self):
        return True

    def __len__(self):
        return True


#: arrow format string for 'day' archives
DAY_FORMAT = 'YYYY-MM-DD'

#: arrow format string for 'month' archives
MONTH_FORMAT = 'YYYY-MM'

#: arrow format string for 'year' archives
YEAR_FORMAT = 'YYYY'

#: arrow format string for 'week' archives
WEEK_FORMAT = 'YYYYMMDD_w'


def parse_date(datestr):
    """ Parse a date expression into a tuple of:

        (start_date, span_type, span_format)

    Arguments:
        datestr -- A date specification, in the format of YYYY-MM-DD (dashes optional)
    """

    match = re.match(
        r'([0-9]{4})(-?([0-9]{1,2}))?(-?([0-9]{1,2}))?(_w)?$', datestr)
    if not match:
        return (arrow.get(datestr,
                          tzinfo=config.timezone).replace(tzinfo=config.timezone),
                'day', 'YYYY-MM-DD')

    year, month, day, week = match.group(1, 3, 5, 6)
    start = arrow.Arrow(year=int(year), month=int(
        month or 1), day=int(day or 1), tzinfo=config.timezone)

    if week:
        return start.span('week')[0], 'week', WEEK_FORMAT
    if day:
        return start, 'day', DAY_FORMAT
    if month:
        return start, 'month', MONTH_FORMAT
    if year:
        return start, 'year', YEAR_FORMAT

    raise ValueError("Could not parse date: {}".format(datestr))


def find_file(path, search_path):
    """ Find a file by relative path. Arguments:

    path -- the image's filename
    search_path -- a list of directories to check in

    Returns: the resolved file path
    """

    for relative in as_list(search_path):
        candidate = os.path.normpath(os.path.join(relative, path))
        if os.path.isfile(candidate):
            return candidate

    return None


def find_entry(rel_path, search_path):
    """ Find an entry by relative path. Arguments:

    path -- the entry's filename (or entry ID)
    search_path -- a list of directories to check in

    Returns: the resolved Entry object
    """

    from . import entry  # pylint:disable=cyclic-import

    try:
        entry_id = int(rel_path)
        record = model.Entry.get(id=entry_id)
        if record:
            return entry.Entry(record)
    except ValueError:
        pass

    if rel_path.startswith('/'):
        search_path = [config.content_folder]
        rel_path = '.' + rel_path

    for where in search_path:
        abspath = os.path.normpath(os.path.join(where, rel_path))
        record = model.Entry.get(file_path=abspath)
        if record:
            return entry.Entry(record)
    return None


def make_slug(title):
    """ convert a title into a URL-friendly slug """
    return slugify.slugify(title)


def static_url(path, absolute=False):
    """ Shorthand for returning a URL for the requested static file.

    Arguments:

    path -- the path to the file (relative to the static files directory)
    absolute -- whether the link should be absolute or relative
    """

    if os.sep != '/':
        path = '/'.join(path.split(os.sep))

    return flask.url_for('static', filename=path, _external=absolute)


def make_tag(name, attrs, start_end=False):
    """ Build an HTML tag from the given name and attributes.

    Arguments:

    name -- the name of the tag (p, div, etc.)
    attrs -- a dict of attributes to apply to the tag
    start_end -- whether this tag should be self-closing

    If an attribute's value is None it will be written as a standalone attribute,
    e.g. <audio controls>. To suppress it entirely, make the value explicitly False.
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
            text += ' {}'.format(key)
            if val is not None:
                import markupsafe
                escaped = html.escape(str(val), False).replace('"', '&#34;')

                if isinstance(val, CallableProxy):
                    val = val()
                if isinstance(val, markupsafe.Markup):
                    # We just double-escaped all entities...
                    escaped = re.sub(r'&amp;([a-zA-Z0-9.\-_\:]+;)', r'&\1', val)
                text += '="{}"'.format(escaped)
    if start_end:
        text += ' /'
    text += '>'
    return flask.Markup(text)


def file_fingerprint(fullpath):
    """ Get a metadata fingerprint for a file """
    stat = os.stat(fullpath)
    return ','.join([str(value) for value in [stat.st_ino, stat.st_mtime, stat.st_size] if value])


def remap_args(input_args, remap):
    """ Generate a new argument list by remapping keys. The 'remap'
    dict maps from destination key -> priority list of source keys
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


def remap_link_target(path, absolute=False):
    """ remap a link target to a static URL if it's prefixed with @ """
    if path.startswith('@'):
        # static resource
        return static_url(path[1:], absolute=absolute)

    if absolute:
        # absolute-ify whatever the URL is
        return urllib.parse.urljoin(flask.request.url, path)

    return path


def get_category(filename):
    """ Get a default category name from a filename in a cross-platform manner """
    return '/'.join(os.path.dirname(filename).split(os.sep))


class HTMLTransform(html.parser.HTMLParser):
    """ Wrapper to HTMLParser to make it easier to build a SAX-style processor.

    You will probably want to implement:
        handle_starttag(self, tag, attrs)
        handle_endtag(self, tag)
        handle_data(self, data)
        handle_startendtag(self, tag, attrs)
    """

    def __init__(self):
        super().__init__()

        self.reset()
        self.strict = False
        self.convert_charrefs = False
        self._fed = []

    def append(self, item):
        """ Append some text to the output """
        self._fed.append(item)

    def get_data(self):
        """ Concatenate the output """
        return ''.join(self._fed)

    def handle_entityref(self, name):
        self.handle_data('&' + name + ';')

    def handle_charref(self, name):
        self.handle_data('&#' + name + ';')

    def error(self, message):
        """ Deprecated, per https://bugs.python.org/issue31844 """
        return message


def prefix_normalize(kwargs):
    """ Given an argument list where one of them is 'prefix', normalize the
    arguments to convert {prefix}{key} to {key} and remove the prefixed versions
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


def is_list(item):
    """ Return if this is a list-type thing """
    return isinstance(item, (list, tuple, set))


def as_list(item):
    """ Return list-type things directly; convert other things into a list """
    if item is None:
        return []

    if is_list(item):
        return item

    return [item]


class CategoryConverter(werkzeug.routing.PathConverter):
    """ A version of PathConverter that doesn't accept paths beginning with _ """

    def to_python(self, value):
        if value[0] == '_':
            raise werkzeug.routing.ValidationError
        return super().to_python(value)


class TemplateConverter(werkzeug.routing.UnicodeConverter):
    """ A version of UnicodeConverter that doesn't accept strings beginning with _ """

    def to_python(self, value):
        if value[0] == '_':
            raise werkzeug.routing.ValidationError
        return super().to_python(value)


def auth_link(endpoint):
    """ Generates a function that maps an optional redir parameter to the specified
    auth endpoint. """

    force_ssl = config.auth.get('AUTH_FORCE_HTTPS', config.auth.get('AUTH_FORCE_SSL'))

    def endpoint_link(redir=None, **kwargs):
        LOGGER.debug("Getting %s for redir=%s kwargs=%s", endpoint, redir, kwargs)
        if redir is None:
            # nothing specified so use the current request path
            redir = flask.request.full_path
        else:
            # resolve CallableProxy if present
            redir = str(redir)
        LOGGER.debug("  Resulting redir = %s", redir)

        # strip off leading slashes
        redir = re.sub(r'^/*', r'', redir)
        # if there's a trailing ? strip that off too
        redir = re.sub(r'\?$', r'', redir)

        if force_ssl and flask.request.scheme != 'https':
            kwargs = {**kwargs,
                      '_external': True,
                      '_scheme': 'https'}

        return flask.url_for(endpoint, redir=redir, **kwargs)

    return CallableProxy(endpoint_link)
