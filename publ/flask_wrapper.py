""" the Flask wrapper class """

import functools
import logging
import re
import typing

import arrow
import flask
import werkzeug.exceptions
from werkzeug.utils import cached_property

# pylint:disable=cyclic-import
from . import (caching, cli, config, html_entry, image, index, maintenance,
               model, rendering, search, tokens, user, utils, view)

LOGGER = logging.getLogger(__name__)


class Publ(flask.Flask):
    """ A Publ application.

    At present, only one Publ application can be instanced at one time.
    """

    _instance = None

    def __init__(self, name, cfg, **kwargs):
        """ Constructor for a Publ application. Accepts the following parameters:

        :param str name: The name of the app
        :param str cfg: Application configuration

        Additional keyword arguments are forwarded along to the Flask constructor.

        Configuration keys:

        * ``database_config``: The database confugiration to be provided to PonyORM.
            See https://docs.ponyorm.org/database.html for more information
        * ``content_folder``: The folder that stores the site content
        * ``template_folder``: The folder that contains the Jinja templates
        * ``static_folder``: The folder that contains static content
        * ``static_url_path``: The URL mount point for the static content folder
        * ``image_output_subdir``: The subdirectory of the static content folder to
            store the image rendition cache
        * ``index_rescan_interval``: How frequently (in seconds) to rescan the
            content index
        * ``index_wait_time``: How long to wait (in seconds) before starting to
            process content updates
        * ``image_cache_interval``: How frequently (in seconds) to clean up the
            image rendition cache
        * ``image_cache_age``: The maximum age (in seconds) of an image rendition
        * ``timezone``: The site's local time zone
        * ``cache``: Page render cache configuration; see
            https://flask-caching.readthedocs.io/en/latest/#configuring-flask-caching
        * ``markdown_extensions``: The extensions to enable by default for the
            Markdown processing library. See https://misaka.61924.nl/#extensions
            for details
        * ``auth``: Authentication configuration. See the `Authl configuration
            documentation <https://authl.readthedocs.io>`_. Additionally, setting
            the key ``AUTH_FORCE_HTTPS`` to a truthy value can be used to force the
            user to switch to a secure connection when they log in, and setting
            ``AUTH_TOKEN_STORAGE`` to a :py:class:`authl.tokens.TokenStore` will
            use that for token storage instead of the default.
        * ``user_list``: The file that configures the user and group list
        * ``admin_group``: The user or group that has full administrative access
            to all entries regardless of permissions
        * ``auth_log_prune_interval``: How frequently to prune the authentication log, in seconds
        * ``auth_log_prune_age``: How long to retain authentication log entries, in seconds
        * ``ticket_lifetime``: How long an IndieAuth ticket lasts, in seconds
        * ``token_lifetime``: How long an IndieAuth token lasts, in seconds
        """
        # pylint:disable=too-many-branches,too-many-statements

        if Publ._instance and Publ._instance is not self:
            LOGGER.warning("Only one Publ app can run at a time (%s,%s)", Publ._instance, self)
        Publ._instance = self

        super().__init__(name,
                         template_folder=cfg.get('template_folder', 'templates'),
                         static_folder=cfg.get('static_folder', 'static'),
                         static_url_path=cfg.get('static_url_path', '/static'),
                         **kwargs)

        self.publ_config = config.Config(cfg)

        if 'AUTH_FORCE_SSL' in self.publ_config.auth:
            raise ValueError('AUTH_FORCE_SSL is deprecated; use AUTH_FORCE_HTTPS instead')

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

        self.add_url_rule('/_async/<path:render_spec>',
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
            get_template=rendering.get_template,
            login=utils.auth_link('login'),
            logout=utils.auth_link('logout'),
            token_endpoint=utils.CallableProxy(lambda: utils.secure_link('tokens')),
            secure_url=utils.secure_link,
        )

        self.jinja_env.filters['strip_html'] = html_entry.strip_html  # pylint: disable=no-member

        caching.init_app(self, self.publ_config.cache)

        def logout(redir=''):
            """ Log out from the thing """
            if flask.request.method == 'POST':
                LOGGER.info("Logging out %s", flask.session.get('me'))
                LOGGER.info("Redir: %s", redir)
                LOGGER.info("Request path: %s", flask.request.path)

                flask.session.pop('me')
                return flask.redirect('/' + redir)

            tmpl = rendering.map_template('/', 'logout')
            return rendering.render_publ_template(tmpl)[0]

        if self.publ_config.auth:
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

            self.add_url_rule('/_tokens', 'tokens', tokens.indieauth_endpoint,
                              methods=['GET', 'POST'])

            self.before_request(user.log_user)

            def add_token_endpoint(response):
                endpoint = utils.secure_link("tokens", _external=True)
                response.headers.add(
                    'Link',
                    f'<{endpoint}>; rel="token_endpoint"')
                return response

            self.after_request(add_token_endpoint)

            # Force the authl instance to load before the first request, after the
            # app has had a chance to set secret_key
            self.before_first_request(lambda: self.auth)
        else:
            # Auth isn't configured, so make some placeholder routes so that
            # url_for doesn't fail and reasonable errors get raised
            def no_auth(redir=''):
                raise werkzeug.exceptions.NotFound()

            for base in ('_login', '_logout'):
                for route in (
                    f'/{base}',
                    f'/{base}/',
                    f'/{base}/<path:redir>',
                ):
                    self.add_url_rule(route, 'login', no_auth, methods=['GET', 'POST'])

        self._maint = maintenance.Maintenance(self)
        self.indexer = index.Indexer(self, self.publ_config.index_wait_time)

        if self.publ_config.index_rescan_interval:
            self._maint.register(functools.partial(index.scan_index,
                                                   self.publ_config.content_folder),
                                 self.publ_config.index_rescan_interval)

        if self.publ_config.image_cache_interval and self.publ_config.image_cache_age:
            self._maint.register(functools.partial(image.clean_cache,
                                                   self.publ_config.image_cache_age),
                                 self.publ_config.image_cache_interval)

        if self.publ_config.auth_log_prune_interval and self.publ_config.auth_log_prune_age:
            self._maint.register(functools.partial(user.prune_log,
                                                   self.publ_config.auth_log_prune_age),
                                 self.publ_config.auth_log_prune_interval)

        self.before_request(self._maint.run)

        if self.debug:
            # We're in debug mode so we don't want to scan until everything's up
            # and running
            self.before_first_request(self._startup)
        else:
            # In production, register the exception handler and scan the index
            # immediately
            self.register_error_handler(Exception, rendering.render_exception)
            self._startup()

        cli.setup(self)

    @cached_property
    def auth(self):
        """ Get the authl instance """
        if self.publ_config.auth:
            try:
                import authl.flask
            except ImportError:
                LOGGER.error(
                    "Authentication system requested, but the dependencies are not installed. "
                    "See https://publ.plaidweb.site/manual/865-Python-API#auth")

            auth_force_https = self.publ_config.auth.get(
                'AUTH_FORCE_HTTPS',
                self.publ_config.auth.get('AUTH_FORCE_SSL'))
            if auth_force_https:
                self.config['SESSION_COOKIE_SECURE'] = True

            return authl.flask.AuthlFlask(
                self, self.publ_config.auth,
                login_path='/_login',
                login_name='login',
                callback_path='/_cb',
                tester_path='/_ct',
                force_https=bool(self.publ_config.auth.get('AUTH_FORCE_HTTPS')),
                login_render_func=rendering.render_login_form,
                on_verified=user.register,
                token_storage=self.publ_config.auth.get('AUTH_TOKEN_STORAGE'))
        return None

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

    def test_path_regex(self, path):
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

    def _startup(self):
        """ Startup routine for initiating the content indexer """

        with self.app_context():
            model.setup(self.publ_config.database_config)

            self.search_index = search.SearchIndex(self.publ_config)
            self.jinja_env.globals.update(  # pylint: disable=no-member
                search=self.search_index.query,
            )

            import click

            ctx = click.get_current_context(silent=True)
            if not ctx or ctx.info_name == 'run':
                index.scan_index(self.publ_config.content_folder)
                if self.publ_config.index_enable_watchdog:
                    index.background_scan(self.publ_config.content_folder)


current_app = typing.cast(Publ, flask.current_app)  # pylint:disable=invalid-name
