# caching.py
""" Useful caching functions """

import os
import hashlib
import datetime

import arrow
from flask_caching import Cache
from flask import request
from pony import orm

from . import config
from . import index
from . import utils
from . import queries
from . import model

cache = Cache()  # pylint: disable=invalid-name


def init_app(app):
    """ Initialize the cache for the app """
    cache.init_app(app, config=config.cache)


def do_not_cache():
    """ Return whether we should cache a page render """

    if index.in_progress():
        # We are reindexing the site
        return True

    if request.if_none_match or request.if_modified_since:
        # we might be returning a 304 NOT MODIFIED based on a client request,
        # and we don't want to cache that as the result for *all* client
        # requests to this URI
        return True

    return False


def get_cache_tag(file, mtime):
    """ Get the ETag,Last-Modified for a file """
    etag = hashlib.md5(utils.file_fingerprint(
        file).encode('utf-8')).hexdigest()[:16]
    return etag, mtime


def get_view_cache_tag(template, entry=None):
    """ Get a pessimistic cache tag for a view

    Arguments:

    template -- the template file being used to render
    entry -- the entry to use; defaults to the most recently-published entry

    Returns (etag,last-modified)
    """

    candidates = []

    # If no entry is specified, check the most recently indexed file
    if index.last_modified.file:
        candidates.append(index.last_modified())

    # check the template file
    candidates.append((template.mtime, template.file_path))

    if entry:
        # Use the entry in question
        entry_file = entry.file_path
        candidates.append((os.stat(entry_file).st_mtime, entry_file))

    # check the most recently-published entry (even on entry views, since this
    # can affect prev/next links)
    with orm.db_session:
        last_published = queries.build_query({}).order_by(
            orm.desc(model.Entry.utc_date))[:1]
        if last_published:
            # We actually want the publish time, not the file modification time
            last_entry = last_published[0]
            last_pubtime = arrow.get(last_entry.utc_date).timestamp
            candidates.append((last_pubtime, last_entry.file_path))

    last_mtime, last_file = max(candidates)
    return get_cache_tag(last_file, last_mtime)


def not_modified(etag, mtime):
    """ Return True if the request indicates that the client's cache is valid """

    if request.if_none_match.contains(etag):
        return True

    if request.if_modified_since:
        mod_time = datetime.datetime.utcfromtimestamp(int(mtime))
        if request.if_modified_since >= mod_time:
            return True

    return False
