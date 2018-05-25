""" Publ entry point """

import time

import arrow
import flask
import werkzeug.exceptions

from . import config, rendering, model, index, caching, view, utils, async


def publ(name, cfg):
    """ Create a Flask app and configure it for use with Publ """

    config.setup(cfg)

    app = flask.Flask(name,
                      template_folder=config.template_folder,
                      static_folder=config.static_folder,
                      static_url_path=config.static_url_path)

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

    app.add_url_rule('/_async/<path:filename>',
                     'async', async.image)

    app.add_url_rule('/_', 'chit', rendering.render_transparent_chit)

    app.config['TRAP_HTTP_EXCEPTIONS'] = True
    app.register_error_handler(
        werkzeug.exceptions.HTTPException, rendering.render_exception)

    if not app.debug:
        app.register_error_handler(Exception, rendering.render_exception)

    app.jinja_env.globals.update(  # pylint: disable=no-member
        get_view=view.get_view,
        arrow=arrow,
        static=utils.static_url
    )

    caching.init_app(app)

    if config.index_rescan_interval:
        app.before_request(scan_index)

    if 'CACHE_THRESHOLD' in config.cache:
        app.after_request(set_cache_expiry)

    app.before_first_request(startup)
    return app


last_scan = None  # pylint: disable=invalid-name


def startup():
    """ Startup routine for initiating the content indexer """
    model.setup()
    scan_index(True)
    index.background_scan(config.content_folder)


def scan_index(force=False):
    """ Rescan the index if it's been more than a minute since the last scan """
    global last_scan  # pylint: disable=invalid-name,global-statement
    now = time.time()
    if force or not last_scan or now - last_scan > config.index_rescan_interval:
        index.scan_index(config.content_folder)
        last_scan = now


def set_cache_expiry(req):
    """ Set the cache control headers """
    if 'CACHE_THRESHOLD' in config.cache:
        req.headers['Cache-Control'] = (
            'public, max-age={}'.format(config.cache['CACHE_THRESHOLD']))
    return req
