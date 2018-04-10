# utils.py
# Some useful utilities that don't belong anywhere else

import config
import re
import arrow

'''
Wrapper class to make args possible on properties
'''
class CallableProxy:
    def __init__(self,func,*args,**kwargs):
        self._func = func
        self._hasDefault = False
        self._default_args = args
        self._default_kwargs = kwargs

    def _get_default(self):
        if not self._hasDefault:
            if self._default_args:
                self._default = self._func(*self._default_args, **self._default_kwargs)
            else:
                self._default = self._func(**self._default_kwargs)
            self._hasDefault = True
        return self._default

    def __call__(self,**kwargs):
        # use the new kwargs to override the defaults
        kwargs = dict(self._default_kwargs, **kwargs)
        return self._func(*self._default_args, **kwargs)

    def __getattr__(self,name):
        return getattr(self._get_default(), name)

    def __nonzero__(self):
        return not not self._get_default()

    def __len__(self):
        return 1 if self._get_default() else 0

    def __str__(self):
        return str(self._get_default())

'''
Parse a date expression into a tuple:

(start_date, span_type, span_format)
'''
def parse_date(datestr):
    match = re.match(r'([0-9]{4})(-?([0-9]{1,2}))?(-?([0-9]{1,2}))?', datestr)
    if not match:
        return (arrow.get(datestr), 'day', 'YYYY-MM-DD')

    year, month, day = match.group(1,3,5)
    start = arrow.Arrow(year=int(year), month=int(month or 1), day=int(day or 1), tzinfo=config.timezone)

    if day:
        return start, 'day', 'YYYY-MM-DD'
    elif month:
        return start, 'month', 'YYYY-MM'
    else:
        return start, 'year', 'YYYY'
