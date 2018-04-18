""" Publ entry point """

import time

import arrow
import flask

import config

from . import rendering, model, index, caching, view, utils
from .caching import cache


def setup(app):
    """ Given a Flask application, configures it for use with Publ. """

    for route in [
            '/',
            '/<path:category>/',
            '/<template>',
            '/<path:category>/<template>',
    ]:
        app.add_url_rule(route, 'category', rendering.render_category)

    for route in [
            '/<int:entry_id>',
            '/<int:entry_id>-<slug_text>',
            '/<path:category>/<int:entry_id>',
            '/<path:category>/<int:entry_id>-<slug_text>',
    ]:
        app.add_url_rule(route, 'entry', rendering.render_entry)

    app.add_url_rule('/<path:path>.PUBL_PATHALIAS',
                     'path_alias', rendering.render_path_alias)

    if not app.debug:
        app.register_error_handler(Exception, rendering.render_exception)

    app.jinja_env.globals.update(
        get_view=view.get_view, arrow=arrow, static=utils.static_url)

    app.before_request(rescan_index)
    app.after_request(set_cache_expiry)

    cache.init_app(app)

    # Scan the index
    model.create_tables()
    index.scan_index(config.content_directory)
    index.background_scan(config.content_directory)


last_scan = None  # pylint: disable=invalid-name


def rescan_index():
    """ Rescan the index if it's been more than a minute since the last scan """
    global last_scan  # pylint: disable=invalid-name,global-statement
    now = time.time()
    if not last_scan or now - last_scan > 60:
        index.scan_index(config.content_directory)
        last_scan = now


def set_cache_expiry(req):
    """ Set the cache control headers """
    req.headers['Cache-Control'] = 'public, max-age=300'
    return req
