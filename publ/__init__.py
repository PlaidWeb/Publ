""" Publ: A Flask-based site management system.

Like a static publishing system, but dynamic! See http://publ.beesbuzz.biz
for more information. """

import functools
import logging
import re
import uuid

import arrow
import authl.flask
import flask
import werkzeug.exceptions

from . import (caching, config, image, index, maintenance, model, rendering,
               tokens, user, utils, view)

LOGGER = logging.getLogger(__name__)


class Publ(flask.Flask):
    """ A Publ application.

    At present, only one Publ application can be instanced at one time.
    """

    _instance = None

    def __init__(self, name, cfg, **kwargs):
        """ Constructor for a Publ application. Accepts the following parameters:

        name -- The name of the app
        cfg -- Application configuration

        Additional keyword arguments are forwarded along to the Flask constructor.

        Configuration keys:

        database_config -- The database confugiration to be provided to PonyORM.
            See https://docs.ponyorm.org/database.html for more information
        content_folder -- The folder that stores the site content
        template_folder -- The folder that contains the Jinja templates
        static_folder -- The folder that contains static content
        static_url_path -- The URL mount point for the static content folder
        image_output_subdir -- The subdirectory of the static content folder to
            store the image rendition cache
        index_rescan_interval -- How frequently (in seconds) to rescan the
            content index
        image_cache_interval -- How frequently (in seconds) to clean up the
            image rendition cache
        image_cache_age -- The maximum age (in seconds) of an image rendition
        timezone -- The site's local time zone
        cache -- Page render cache configuration; see
            https://flask-caching.readthedocs.io/en/latest/#configuring-flask-caching
        markdown_extensions -- The extensions to enable by default for the
            Markdown processing library. See https://misaka.61924.nl/#extensions
            for details
        secret_key -- Authentication signing secret. This should remain private.
            The default value is randomly generated at every application restart.
        auth -- Authentication configuration. See the Authl configuration
            documentation at [link TBD]. Additionally, setting the key
            AUTH_FORCE_HTTPS to a truthy value can be used to force the user to
            switch to an SSL connection when they log in.
        user_list -- The file that configures the user and group list
        admin_group -- The user or group that has full administrative access
            to all entries regardless of permissions
        auth_log_prune_interval -- How frequently to prune the authentication log, in seconds
        auth_log_prune_age -- How long to retain authentication log entries, in seconds
        max_token_age -- The maximum lifetime of AutoAuth tokens
        """
        # pylint:disable=too-many-branches,too-many-statements

        if Publ._instance and Publ._instance is not self:
            raise RuntimeError("Only one Publ app can run at a time")
        Publ._instance = self

        config.setup(cfg)  # https://github.com/PlaidWeb/Publ/issues/113

        super().__init__(name,
                         template_folder=config.template_folder,
                         static_folder=config.static_folder,
                         static_url_path=config.static_url_path,
                         **kwargs)

        if 'AUTH_FORCE_SSL' in config.auth:
            LOGGER.warning("""The configuration key AUTH_FORCE_SSL has been \
deprecated in favor of AUTH_FORCE_HTTPS. Please change your configuration \
accordingly.

This configuration value will stop being supported in Publ 0.6.
""")

        auth_force_https = config.auth.get('AUTH_FORCE_HTTPS',
                                           config.auth.get('AUTH_FORCE_SSL'))
        if auth_force_https:
            self.config['SESSION_COOKIE_SECURE'] = True

        if 'secret_key' in cfg:
            LOGGER.warning("""secret_key is no longer configured in the configuration \
dictionary; please configure it by setting the secret_key property on the Publ object \
after initialization.

This configuration value will stop being supported in Publ 0.6.
""")
            self.secret_key = cfg['secret_key']
        else:
            self.secret_key = uuid.uuid4().bytes

        self._regex_map = []

        self.url_map.converters['category'] = utils.CategoryConverter
        self.url_map.converters['template'] = utils.TemplateConverter

        for route in [
                '/',
                '/<category:category>/',
                '/<template:template>',
                '/<category:category>/<template:template>',
        ]:
            self.add_url_rule(route, 'category', rendering.render_category)

        for route in [
                '/<int:entry_id>',
                '/<int:entry_id>-',
                '/<int:entry_id>-<slug_text>',
                '/<category:category>/<int:entry_id>',
                '/<category:category>/<int:entry_id>-',
                '/<category:category>/<int:entry_id>-<slug_text>',
        ]:
            self.add_url_rule(route, 'entry', rendering.render_entry)

        self.add_url_rule('/<path:path>.PUBL_PATHALIAS',
                          'path_alias', rendering.render_path_alias)

        self.add_url_rule('/_async/<path:filename>',
                          'async', image.get_async)

        self.add_url_rule('/_', 'chit', rendering.render_transparent_chit)

        self.add_url_rule('/_file/<path:filename>',
                          'asset', rendering.retrieve_asset)

        self.add_url_rule('/_token', 'token', tokens.token_endpoint, methods=['POST'])

        self.config['TRAP_HTTP_EXCEPTIONS'] = True
        self.register_error_handler(
            werkzeug.exceptions.HTTPException, rendering.render_exception)

        self.jinja_env.globals.update(  # pylint: disable=no-member
            get_view=view.get_view,
            arrow=arrow,
            static=utils.static_url,
            get_template=rendering.get_template,
            login=utils.auth_link('login'),
            logout=utils.auth_link('logout')
        )

        caching.init_app(self, config.cache)

        self.authl = authl.flask.AuthlFlask(self, config.auth,
                                            login_path='/_login',
                                            login_name='login',
                                            callback_path='/_cb',
                                            tester_path='/_ct',
                                            force_ssl=auth_force_https,
                                            login_render_func=rendering.render_login_form)

        def logout(redir=''):
            """ Log out from the thing """
            if flask.request.method == 'POST':
                LOGGER.info("Logging out")
                LOGGER.info("Redir: %s", redir)
                LOGGER.info("Request path: %s", flask.request.path)

                flask.session['me'] = ''
                return flask.redirect('/' + redir)

            tmpl = rendering.map_template('/', 'logout')
            return rendering.render_publ_template(tmpl)[0]

        for route in [
                '/_logout',
                '/_logout/',
                '/_logout/<path:redir>'
        ]:
            self.add_url_rule(route, 'logout', logout, methods=['GET', 'POST'])

        for route in [
                '/_admin',
                '/_admin/<by>'
        ]:
            self.add_url_rule(route, 'admin', rendering.admin_dashboard)

        self.before_request(user.log_user)
        self.after_request(tokens.inject_auth_headers)

        self._maint = maintenance.Maintenance()

        if config.index_rescan_interval:
            self._maint.register(functools.partial(index.scan_index,
                                                   config.content_folder),
                                 config.index_rescan_interval)

        if config.image_cache_interval and config.image_cache_age:
            self._maint.register(functools.partial(image.clean_cache,
                                                   config.image_cache_age),
                                 config.image_cache_interval)

        if config.auth_log_prune_interval and config.auth_log_prune_age:
            self._maint.register(functools.partial(user.prune_log,
                                                   config.auth_log_prune_age),
                                 config.auth_log_prune_interval)

        self.before_request(self._maint.run)

        if 'CACHE_THRESHOLD' in config.cache:
            self.after_request(self._set_cache_expiry)

        if self.debug:
            # We're in debug mode so we don't want to scan until everything's up
            # and running
            self.before_first_request(self._startup)
        else:
            # In production, register the exception handler and scan the index
            # immediately
            self.register_error_handler(Exception, rendering.render_exception)
            self._startup()

    def path_alias_regex(self, regex):
        r""" A decorator that adds a path-alias regular expression; calls
        add_path_regex.

        Example usage:

        @app.path_alias_regex(r'/d/([0-9]{8}(_w)?)\.php')
        def redirect_date(match):
            return flask.url_for('category', category='comics',
                                 date=match.group(1)), True
        """
        def decorator(func):
            """ Adds the function to the regular expression alias list """
            return self.add_path_regex(regex, func)
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
        return func

    def _test_path_regex(self, path):
        """ Evaluate the registered path-alias regular expressions. Returns the
        result of the first handler that successfully matches the path.
        """
        for regex, func in self._regex_map:
            match = re.match(regex, path)
            if match:
                dest, permanent = func(match)
                if dest:
                    return dest, permanent

        return None, None

    @staticmethod
    def _startup():
        """ Startup routine for initiating the content indexer """
        model.setup()
        index.scan_index(config.content_folder)
        index.background_scan(config.content_folder)

    @staticmethod
    def _set_cache_expiry(response):
        """ Set the cache control headers """
        if response.cache_control.max_age is None and 'CACHE_DEFAULT_TIMEOUT' in config.cache:
            response.cache_control.max_age = config.cache['CACHE_DEFAULT_TIMEOUT']
        return response


def publ(name, cfg):
    """ Legacy function that originally did a lot more """
    LOGGER.warning("This function is deprecated; use publ.Publ instead")
    return Publ(name, cfg)
