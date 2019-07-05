""" Publ entry point """

import re
import functools
import logging

import arrow
import flask
import werkzeug.exceptions
import authl

from . import config, rendering, model, index, caching, view, utils
from . import maintenance, image

LOGGER = logging.getLogger(__name__)


class Publ(flask.Flask):
    """ A Publ app; extends Flask so that we can add our own custom decorators """

    _instance = None

    def __init__(self, name, cfg, *args, **kwargs):
        if Publ._instance and Publ._instance is not self:
            raise RuntimeError("Only one Publ app can run at a time")
        Publ._instance = self

        config.setup(cfg)  # https://github.com/PlaidWeb/Publ/issues/113

        super().__init__(name,
                         template_folder=config.template_folder,
                         static_folder=config.static_folder,
                         static_url_path=config.static_url_path, *args, **kwargs)

        self.secret_key = config.secret_key

        self._regex_map = []

        for route in [
                '/',
                '/<path:category>/',
                '/<template>',
                '/<path:category>/<template>',
        ]:
            self.add_url_rule(route, 'category', rendering.render_category)

        for route in [
                '/<int:entry_id>',
                '/<int:entry_id>-',
                '/<int:entry_id>-<slug_text>',
                '/<path:category>/<int:entry_id>',
                '/<path:category>/<int:entry_id>-',
                '/<path:category>/<int:entry_id>-<slug_text>',
        ]:
            self.add_url_rule(route, 'entry', rendering.render_entry)

        self.add_url_rule('/<path:path>.PUBL_PATHALIAS',
                          'path_alias', rendering.render_path_alias)

        self.add_url_rule('/_async/<path:filename>',
                          'async', image.get_async)

        self.add_url_rule('/_', 'chit', rendering.render_transparent_chit)

        self.add_url_rule('/_file/<path:filename>',
                          'asset', rendering.retrieve_asset)

        self.config['TRAP_HTTP_EXCEPTIONS'] = True
        self.register_error_handler(
            werkzeug.exceptions.HTTPException, rendering.render_exception)

        self.jinja_env.globals.update(  # pylint: disable=no-member
            get_view=view.get_view,
            arrow=arrow,
            static=utils.static_url,
            get_template=rendering.get_template
        )

        if config.cache:
            caching.init_app(self, config.cache)

        if config.auth:
            authl.setup_flask(self, config.auth)

        self._maint = maintenance.Maintenance()

        if config.index_rescan_interval:
            self._maint.register(functools.partial(index.scan_index,
                                                   config.content_folder),
                                 config.index_rescan_interval)

        if config.image_cache_interval and config.image_cache_age:
            self._maint.register(functools.partial(image.clean_cache,
                                                   config.image_cache_age),
                                 config.image_cache_interval)

        self.before_request(self._maint.run)

        if 'CACHE_THRESHOLD' in config.cache:
            self.after_request(self.set_cache_expiry)

        if self.debug:
            # We're in debug mode so we don't want to scan until everything's up
            # and running
            self.before_first_request(self.startup)
        else:
            # In production, register the exception handler and scan the index
            # immediately
            self.register_error_handler(Exception, rendering.render_exception)
            self.startup()

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

    @staticmethod
    def startup():
        """ Startup routine for initiating the content indexer """
        model.setup()
        index.scan_index(config.content_folder)
        index.background_scan(config.content_folder)

    @staticmethod
    def set_cache_expiry(response):
        """ Set the cache control headers """
        if response.cache_control.max_age is None and 'CACHE_DEFAULT_TIMEOUT' in config.cache:
            response.cache_control.max_age = config.cache['CACHE_DEFAULT_TIMEOUT']
        return response


def publ(name, cfg):
    """ Legacy function that originally did a lot more """
    LOGGER.warning("This function is deprecated; use publ.Publ instead")
    return Publ(name, cfg)
