# utils.py
# Some useful utilities that don't belong anywhere else


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
        return self._get_default() and 1 or 0

    def __str__(self):
        return str(self._get_default())
