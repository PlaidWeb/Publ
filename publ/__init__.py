""" Publ entry point """

import arrow
import flask

import config

from . import rendering, model, index, caching, view
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
        get_view=view.get_view, arrow=arrow, static=rendering.static_url)

    cache.init_app(app)

    # Scan the index
    model.create_tables()
    index.scan_index(config.content_directory)
    index.background_scan(config.content_directory)
