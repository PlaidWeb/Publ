# utils.py
""" Some useful utilities that don't belong anywhere else """

from __future__ import absolute_import, with_statement

import re
import os
import html
import urllib.parse

import arrow
import flask
import slugify

from . import config


class CallableProxy:
    """ Wrapper class to make args possible on properties """
    # pylint: disable=too-few-public-methods

    def __init__(self, func, *args, **kwargs):
        """ Construct the property proxy.

        func -- The function to wrap
        args -- Default positional arguments for the function call
        kwargs -- Default keyword arguments for the function call
        """

        self._func = func if func else (lambda **kwargs: '')
        self._has_default = False
        self._default_args = args
        self._default_kwargs = kwargs

    def _get_default(self):
        """ Get the default function return """

        # pylint: disable=attribute-defined-outside-init
        if not self._has_default:
            if self._default_args:
                self._default = self._func(
                    *self._default_args,
                    **self._default_kwargs)
            else:
                self._default = self._func(**self._default_kwargs)
            self._has_default = True
        return self._default

    def __call__(self, *args, **kwargs):
        # use the new kwargs to override the defaults
        kwargs = dict(self._default_kwargs, **kwargs)

        # override args as well
        pos_args = [*args, *self._default_args[len(args):]]

        return self._func(*pos_args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._get_default(), name)

    def __nonzero__(self):
        return self._get_default().__nonzero__()

    def __len__(self):
        return 1 if self._get_default() else 0

    def __str__(self):
        return str(self._get_default())

    def __iter__(self):
        return self._get_default().__iter__()


class TrueCallableProxy(CallableProxy):
    """ A version of CallableProxy that is always truthy """
    # pylint: disable=too-few-public-methods

    def __nonzero__(self):
        return True

    def __len__(self):
        return True

#: arrow format string for 'day' archives
DAY_FORMAT = 'YYYY-MM-DD'

#: arrow format string for 'month' archives
MONTH_FORMAT = 'YYYY-MM'

#: arrow format string for 'year' archives
YEAR_FORMAT = 'YYYY'


def parse_date(datestr):
    """ Parse a date expression into a tuple of:

        (start_date, span_type, span_format)

    Arguments:
        datestr -- A date specification, in the format of YYYY-MM-DD (dashes optional)
    """

    match = re.match(r'([0-9]{4})(-?([0-9]{1,2}))?(-?([0-9]{1,2}))?$', datestr)
    if not match:
        return (arrow.get(datestr,
                          tzinfo=config.timezone).replace(tzinfo=config.timezone),
                'day', 'YYYY-MM-DD')

    year, month, day = match.group(1, 3, 5)
    start = arrow.Arrow(year=int(year), month=int(
        month or 1), day=int(day or 1), tzinfo=config.timezone)

    if day:
        return start, 'day', DAY_FORMAT
    elif month:
        return start, 'month', MONTH_FORMAT
    elif year:
        return start, 'year', YEAR_FORMAT

    raise ValueError("Could not parse date: {}".format(datestr))


def find_file(path, search_path):
    """ Find a file by relative path. Arguments:

    path -- the image's filename
    search_path -- a list of directories to check in

    Returns: the resolved file path
    """

    if isinstance(search_path, str):
        search_path = [search_path]
    for relative in search_path:
        candidate = os.path.normpath(os.path.join(relative, path))
        if os.path.isfile(candidate):
            return candidate

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
    return flask.url_for('static', filename=path, _external=absolute)


def make_tag(name, attrs, start_end=False):
    """ Build an HTML tag from the given name and attributes.

    Arguments:

    name -- the name of the tag (p, div, etc.)
    attrs -- a dict of attributes to apply to the tag
    start_end -- whether this tag should be self-closing
    """

    text = '<' + name
    for key, val in attrs.items():
        if val is not None:
            text += ' {}="{}"'.format(key, html.escape(str(val)))
    if start_end:
        text += ' /'
    text += '>'
    return text


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
        if isinstance(src_keys, str):
            src_keys = [src_keys]

        for key in src_keys:
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
