# caching.py
# Where the cache lives

import config
from flask.ext.cache import Cache
from flask import request

cache = Cache(config=config.cache)

''' Key generator for categories '''
def make_category_key():
    return 'category/' + request.full_path

''' Key generator for entries '''
def make_entry_key():
    return 'entry/' + request.path

