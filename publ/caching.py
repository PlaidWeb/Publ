# caching.py
""" Useful caching functions """

from flask_cache import Cache
from flask import request

from . import config

cache = Cache(config=config.cache)  # pylint: disable=invalid-name


def make_category_key():
    """ Key generator for categories """
    return 'category/' + request.full_path


def make_entry_key():
    """ Key generator for entries """
    return 'entry/' + request.path
