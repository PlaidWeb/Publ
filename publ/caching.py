# caching.py
""" Useful caching functions """

import hashlib
from abc import ABC, abstractmethod

from flask_caching import Cache
from flask import request

from . import config

cache = Cache()  # pylint: disable=invalid-name


def init_app(app):
    """ Initialize the cache for the app """
    cache.init_app(app, config=config.cache)


def do_not_cache():
    """ Return whether we should cache a page render """

    from . import index  # pylint: disable=cyclic-import

    if index.in_progress():
        # We are reindexing the site
        return True

    if request.if_none_match or request.if_modified_since:
        # we might be returning a 304 NOT MODIFIED based on a client request,
        # and we don't want to cache that as the result for *all* client
        # requests to this URI
        return True

    return False


def not_modified(etag):
    """ Return True if the request indicates that the client's cache is valid """

    if request.if_none_match.contains(etag):
        return True

    return False


def get_etag(text):
    """ Compute the etag for the rendered text"""

    return hashlib.md5(text.encode('utf-8')).hexdigest()


class Memoizable(ABC):
    """ Add this interface to a method to make it stably memoizable with the declared _key """

    @abstractmethod
    def _key(self):
        pass

    def __repr__(self):
        return repr(self._key())

    def __hash__(self):
        return hash(self._key())

    def __eq__(self, other):
        # pylint: disable=protected-access
        return self._key() == other._key()
