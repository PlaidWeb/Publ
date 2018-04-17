# utils.py
""" Some useful utilities that don't belong anywhere else """

import re

import arrow

import config


class CallableProxy:
    """ Wrapper class to make args possible on properties """
    # pylint: disable=too-few-public-methods

    def __init__(self, func, *args, **kwargs):
        """ Construct the property proxy.

        func -- The function to wrap
        args -- Default positional arguments for the function call
        kwargs -- Default keyword arguments for the function call
        """

        self._func = func
        self._has_default = False
        self._default_args = args
        self._default_kwargs = kwargs

    def _get_default(self):
        """ Get the default function return """

        # pylint: disable=attribute-defined-outside-init
        if not self._has_default:
            if self._default_args:
                self._default = self._func(
                    *self._default_args, **self._default_kwargs)
            else:
                self._default = self._func(**self._default_kwargs)
            self._has_default = True
        return self._default

    def __call__(self, **kwargs):
        # use the new kwargs to override the defaults
        kwargs = dict(self._default_kwargs, **kwargs)
        return self._func(*self._default_args, **kwargs)

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


def parse_date(datestr):
    """ Parse a date expression into a tuple of:

        (start_date, span_type, span_format)

    Arguments:
        datestr -- A date specification, in the format of YYYY-MM-DD (dashes optional)
    """

    match = re.match(r'([0-9]{4})(-?([0-9]{1,2}))?(-?([0-9]{1,2}))?$', datestr)
    if not match:
        return (arrow.get(datestr), 'day', 'YYYY-MM-DD')

    year, month, day = match.group(1, 3, 5)
    start = arrow.Arrow(year=int(year), month=int(
        month or 1), day=int(day or 1), tzinfo=config.timezone)

    if day:
        return start, 'day', 'YYYY-MM-DD'
    elif month:
        return start, 'month', 'YYYY-MM'
    elif year:
        return start, 'year', 'YYYY'

    return ValueError("Could not parse date: {}".format(datestr))
