# utils.py
# Some useful utilities that don't belong anywhere else


'''
A utility class for template handlers; turns the stringify operator into a call

This should probably be rewritten to take a callable as the init param instead
'''
class SelfStrCall:
    def __str__(self):
        return self()

'''
Wrapper class to make args possible on properties
'''
class CallableProxy:
    def __init__(self,func):
        self._func = func
        self._hasDefault = False

    def _get_default(self):
        if not self._hasDefault:
            self._default = self._func()
            self._hasDefault = True
        return self._default

    def __call__(self,**kwargs):
        # Always cache a call that takes no extra args
        if not kwargs:
            return self._get_default()
        return self._func(**kwargs)

    def __getattr__(self,name):
        return getattr(self._get_default(), name)

    def __nonzero__(self):
        return not not self._get_default()

    def __len__(self):
        return self._get_default() and 1 or 0
