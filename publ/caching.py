# caching.py
""" Useful caching functions """

import hashlib
from abc import ABC, abstractmethod

from flask import request
from flask_caching import Cache

cache = Cache()  # pylint: disable=invalid-name


def init_app(app, config):
    """ Initialize the cache for the app """
    cache.init_app(app, config=config)


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
    """ Add this interface to a class to make it stably memoizable. """

    @abstractmethod
    def _key(self):
        """
            This should return a value that will be unique across all
            objects of this class.
        """

    def __repr__(self):
        return "{c}({k})".format(c=self.__class__.__name__,
                                 k=self._key()).replace(' ', '_')

    def __hash__(self):
        return hash(self._key())

    def __eq__(self, other):
        # pylint: disable=protected-access
        return self._key() == other._key()
