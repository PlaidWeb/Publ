""" Publ entry point """

import re
import functools

import arrow
import flask
import werkzeug.exceptions

from . import config, rendering, model, index, caching, view, utils
from . import maintenance, image

__version__ = '0.4.0'


class _PublApp(flask.Flask):
    """ A Publ app; extends Flask so that we can add our own custom decorators """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._regex_map = []

    def path_alias_regex(self, regex):
        """ A decorator that adds a path-alias regular expression; calls
        add_path_regex """
        def decorator(func):
            """ Adds the function to the regular expression alias list """
            self.add_path_regex(regex, func)
        return decorator

    def add_path_regex(self, regex, func):
        """ Add a path-alias regex callback to the request router. Takes the
        following arguments:

        regex -- The regular expression for the path-alias hook
        f -- A function taking a `re.match` object on successful match, and
            returns a tuple of `(url, is_permanent)`; url can be `None` if the
            function decides it should not redirect after all.

        The function may also use `flask.request.args` or the like if it needs
        to make a determination based on query args.
        """
        self._regex_map.append((regex, func))

    def get_path_regex(self, path):
        """ Evaluate the registered path-alias regular expressions """
        for regex, func in self._regex_map:
            match = re.match(regex, path)
            if match:
                return func(match)

        return None, None


def publ(name, cfg):
    """ Create a Flask app and configure it for use with Publ """

    config.setup(cfg)

    app = _PublApp(name,
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
            '/<int:entry_id>-',
            '/<int:entry_id>-<slug_text>',
            '/<path:category>/<int:entry_id>',
            '/<path:category>/<int:entry_id>-',
            '/<path:category>/<int:entry_id>-<slug_text>',
    ]:
        app.add_url_rule(route, 'entry', rendering.render_entry)

    app.add_url_rule('/<path:path>.PUBL_PATHALIAS',
                     'path_alias', rendering.render_path_alias)

    app.add_url_rule('/_async/<path:filename>',
                     'async', image.get_async)

    app.add_url_rule('/_', 'chit', rendering.render_transparent_chit)

    app.add_url_rule('/_file/<path:filename>',
                     'asset', rendering.retrieve_asset)

    app.config['TRAP_HTTP_EXCEPTIONS'] = True
    app.register_error_handler(
        werkzeug.exceptions.HTTPException, rendering.render_exception)

    app.jinja_env.globals.update(  # pylint: disable=no-member
        get_view=view.get_view,
        arrow=arrow,
        static=utils.static_url,
        get_template=rendering.get_template
    )

    caching.init_app(app)

    maint = maintenance.Maintenance()

    if config.index_rescan_interval:
        maint.register(functools.partial(index.scan_index,
                                         config.content_folder),
                       config.index_rescan_interval)

    if config.image_cache_interval and config.image_cache_age:
        maint.register(functools.partial(image.clean_cache,
                                         config.image_cache_age),
                       config.image_cache_interval)

    app.before_request(maint.run)

    if 'CACHE_THRESHOLD' in config.cache:
        app.after_request(set_cache_expiry)

    if app.debug:
        # We're in debug mode so we don't want to scan until everything's up
        # and running
        app.before_first_request(startup)
    else:
        # In production, register the exception handler and scan the index
        # immediately
        app.register_error_handler(Exception, rendering.render_exception)
        startup()

    return app


last_scan = None  # pylint: disable=invalid-name


def startup():
    """ Startup routine for initiating the content indexer """
    model.setup()
    index.scan_index(config.content_folder)
    index.background_scan(config.content_folder)


def set_cache_expiry(response):
    """ Set the cache control headers """
    if response.cache_control.max_age is None and 'CACHE_DEFAULT_TIMEOUT' in config.cache:
        response.cache_control.max_age = config.cache['CACHE_DEFAULT_TIMEOUT']
    return response
