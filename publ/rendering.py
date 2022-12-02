# rendering.py
""" Rendering functions """

import base64
import logging
import os
import typing
from typing import Optional

import flask
import werkzeug.exceptions as http_error
from flask import redirect, request, send_file, url_for
from pony import orm

from . import (__version__, caching, image, index, model, path_alias, queries,
               user, utils, view)
from .caching import cache
from .category import Category
from .config import config
from .entry import Entry
from .entry import expire_record as entry_expire_record
from .template import Template, map_template

LOGGER = logging.getLogger(__name__)

# mapping from template extension to MIME type; probably could be better
EXTENSION_MAP = {
    '.html': 'text/html; charset=utf-8',
    '.xml': 'application/xml',
    '.json': 'application/json',
    '.css': 'text/css; charset=utf-8',
    '.txt': 'text/plain; charset=utf-8'
}

# Headers for responses that shouldn't be cached
NO_CACHE = {
    'Cache-control': 'private, no-cache, no-store, max-age=0',
    'X-Robots-Tag': 'noindex,noarchive'
}


def mime_type(template: Template) -> str:
    """ infer the content-type from the extension """
    _, ext = os.path.splitext(template.filename)
    return EXTENSION_MAP.get(ext, 'text/html; charset=utf-8')


def get_template(template: str, relation) -> typing.Optional[str]:
    """ Given an entry or a category, return the path to a related template """
    if isinstance(relation, Entry):
        path = relation.category.path
    elif isinstance(relation, Category):
        path = relation.path
    else:
        path = relation

    tmpl = map_template(path, template)
    return tmpl.filename if tmpl else None


def handle_path_alias(path: Optional[str] = None):
    """ Check to see if the current request is a redirection """
    alias = path_alias.get_alias(path or request.path)

    if isinstance(alias, path_alias.Response):
        return alias.response
    if isinstance(alias, path_alias.RenderEntry):
        return render_entry_record(alias.entry, alias.category, alias.template, _mounted=True)
    if isinstance(alias, path_alias.RenderCategory):
        return render_category_path(alias.category, alias.template)
    if isinstance(alias, path_alias.AuthFailed):
        return handle_unauthorized(alias.cur_user, category=alias.category)

    return None


def image_function(template=None,
                   entry=None,
                   category=None) -> typing.Callable[[str], image.Image]:
    """ Get a function that gets an image """

    path: typing.Tuple[str, ...] = ()

    if entry is not None:
        path += entry.search_path
    if category is not None:
        # Since the category might be different than the entry's category we add
        # this too
        path += (category.search_path,)
    if template is not None:
        path += (os.path.join(config.content_folder,
                              os.path.dirname(template.filename)),)

    return lambda filename: image.get_image(filename, path)


def render_publ_template(template: Template, **kwargs) -> typing.Tuple[str, str]:
    """ Render out a template, providing the image function based on the args.

    Returns tuple of (rendered text, etag)
    """
    @cache.memoize(unless=caching.do_not_cache)
    def do_render(template: Template, **kwargs) -> typing.Tuple[str, str, typing.Dict]:
        LOGGER.debug("Rendering template %s with args %s and kwargs %s; caching=%s",
                     template, request.args, kwargs, not caching.do_not_cache)

        args = {
            'template': template,
            'image': image_function(
                template=template,
                category=kwargs.get('category'),
                entry=kwargs.get('entry')),
            **kwargs
        }

        text = template.render(**args)
        return text, caching.get_etag(text), flask.g.get('needs_auth')

    @orm.db_session
    def latest_entry():
        # Cache-busting query based on most recently-visible entry
        cb_query = queries.build_query({})
        cb_query = cb_query.order_by(orm.desc(model.Entry.utc_timestamp))
        latest = cb_query.first()
        if latest:
            LOGGER.debug("Most recently-scheduled entry: %s", latest)
            return latest.id
        return None

    try:
        cur_user = user.get_active()
        text, etag, flask.g.needs_auth = do_render(  # pylint:disable=assigning-non-slot
            template,
            user=cur_user,
            _user_auth=cur_user.auth_groups if cur_user else None,
            _url=request.url,
            _index_time=index.last_indexed(),
            _latest=latest_entry(),
            _publ_version=__version__.__version__,
            **kwargs)
        return text, etag
    except queries.InvalidQueryError as err:
        raise http_error.BadRequest(str(err))


@orm.db_session
def render_error(category, error_message, error_codes,
                 exception=None,
                 headers=None) -> typing.Tuple[str, int, typing.Dict[str, str]]:
    """ Render an error page.

    Arguments:

    category -- The category of the request
    error_message -- The message to provide to the error template
    error_codes -- The applicable HTTP error code(s). Will usually be an
        integer or a list of integers; the HTTP error response will always
        be the first error code in the list, and the others are alternates
        for looking up the error template to use.
    exception -- Any exception that led to this error page

    Returns a tuple of (rendered_text, status_code, headers)
    """

    LOGGER.info("Rendering error: category=%s error_message='%s' error_codes=%s exception=%s",
                category,
                error_message,
                error_codes,
                exception)

    error_codes = utils.as_list(error_codes)

    error_code = error_codes[0]
    template_list = [str(code) for code in error_codes]
    template_list.append(str(int(error_code / 100) * 100))
    template_list.append('error')

    template = map_template(category, template_list)
    if template:
        return render_publ_template(
            template,
            category=Category.load(category),
            error={'code': error_code, 'message': error_message},
            exception=exception)[0], error_code, headers

    return f'{error_code} {error_message}', error_code, headers


@orm.db_session
def render_exception(error):
    """ Catch-all renderer for the top-level exception handler """

    LOGGER.debug("render_exception %s %s", type(error), error)

    if isinstance(error, http_error.Unauthorized):
        from .flask_wrapper import current_app as app

        force_ssl = config.auth.get('AUTH_FORCE_HTTPS')
        if force_ssl and request.scheme != 'https':
            return redirect(utils.secure_link(request.endpoint,
                                              **request.view_args,
                                              **request.args))

        flask.g.needs_token = True  # pylint:disable=assigning-non-slot
        if app.auth:
            return app.auth.render_login_form(
                destination='/' + utils.redir_path(),
                error=flask.g.get('token_error')), 401

    result = handle_path_alias()
    if result:
        return result

    # Effectively strip off the leading '/', so map_template can decide
    # what the actual category is
    category = request.path[1:]

    qsize = index.queue_size()
    if isinstance(error, http_error.NotFound) and (qsize or index.in_progress()):
        retry = max(5, qsize / 5)
        return render_error(
            category, "Site reindex in progress", 503,
            exception={
                'type': 'Service Unavailable',
                'str': "The site's contents are not fully known; please try again later (qs="
                + str(qsize) + ")",
                'qsize': qsize
            },
            headers={
                **NO_CACHE,
                'Retry-After': retry,
                'Refresh': retry
            })

    if isinstance(error, http_error.HTTPException):
        return render_error(category, error.name, error.code, exception={
            'type': type(error).__name__,
            'str': error.description,
            'args': error.args
        })

    return render_error(category, "Exception Occurred", 500, exception={
        'type': type(error).__name__,
        'str': str(error),
        'args': error.args
    })


@orm.db_session
def render_path_alias(path):
    """ Render a known path-alias (used primarily for forced .php redirects) """

    result = handle_path_alias(path)
    if result:
        return result
    raise http_error.NotFound("Path redirection not found")


@orm.db_session(retry=5)
def render_category(category='', template=None):
    """ Render a category page.

    Arguments:

    category -- The category to render
    template -- The template to render it with
    """
    # pylint:disable=too-many-return-statements

    # See if this is an aliased path
    result = handle_path_alias()
    if result:
        return result

    # Forbidden template types
    if template in ['entry', 'error', 'login', 'unauthorized', 'logout']:
        LOGGER.info("Attempted to render special template %s", template)
        raise http_error.Forbidden("Invalid view requested")

    return render_category_path(category, template)


def render_category_path(category: str, template: typing.Optional[str]):
    """ Renders the actual category by path """
    import arrow

    if category:
        # See if there's any entries for the view...
        if not model.Entry.select(lambda e: (e.category == category
                                             or e.category.startswith(category + '/'))
                                  and e.visible).exists():
            raise http_error.NotFound("No such category")

    if not template:
        template = Category.load(category).get('Index-Template') or 'index'

    tmpl = map_template(category, template)

    if not tmpl:
        # this might actually be a malformed category URL
        test_path = '/'.join((category, template)) if category else template
        LOGGER.debug("Checking for malformed category %s", test_path)
        record = model.Entry.select(lambda e: e.category ==
                                    test_path and e.visible).exists()  # type:ignore
        if record:
            LOGGER.debug("Redirecting to category %s; request.args=%s", test_path, request.args)
            return redirect(url_for('category', category=test_path,
                                    **request.args.to_dict(False)), code=301)  # type:ignore

        # nope, we just don't know what this is
        raise http_error.NotFound(f"No such view '{template}'")

    view_spec = view.parse_view_spec(request.args)
    view_spec['category'] = category
    try:
        view_obj = view.View.load(view_spec)
    except arrow.parser.ParserError as error:
        raise http_error.BadRequest("Invalid date") from error
    except queries.InvalidQueryError as err:
        raise http_error.BadRequest(str(err))

    rendered, etag = render_publ_template(
        tmpl,
        category=Category.load(category),
        view=view_obj)

    if request.if_none_match.contains(etag):
        return 'Not modified', 304, {'ETag': f'"{etag}"'}

    return rendered, {'Content-Type': mime_type(tmpl),
                      'ETag': f'"{etag}"'}


@ orm.db_session
def render_login_form(redir=None, **kwargs):
    """ Renders the login form using the mapped login template """

    # If the user is already logged in, just redirect them to where they're
    # going; if they weren't authorized then they'll just get the unauthorized
    # view.
    LOGGER.debug('redir=%s user=%s', redir, user.get_active())
    if redir is not None and user.get_active():
        return redirect(redir)

    tmpl = map_template('', 'login')
    if not tmpl:
        # fall back to the default Authl handler
        return None
    return render_publ_template(tmpl, redir=redir, **kwargs)[0]


def handle_unauthorized(cur_user, category='', **kwargs):
    """ Handle an unauthorized access to a page """

    if cur_user:
        # User is logged in already
        tmpl = map_template(category, 'unauthorized')
        if not tmpl:
            # Use the default error handler
            raise http_error.Forbidden(f"User {cur_user.name} does not have access")

        # Render the category's unauthorized template
        return render_publ_template(tmpl,
                                    category=Category.load(category),
                                    **kwargs)[0], 403, NO_CACHE

    # User is not already logged in, so present a login page
    raise http_error.Unauthorized()


def _check_authorization(record, category):
    """ Check the auth of an entry against the current user """
    if record.auth:
        cur_user = user.get_active()
        authorized = record.is_authorized(cur_user)

        user.log_access(record, cur_user, authorized)

        if not authorized:
            return handle_unauthorized(cur_user,
                                       entry=Entry.load(record),
                                       category=category)
    return None


def _check_canon_entry_url(record):
    """ Check to see if an entry is being requested at its canonical URL """
    if record.canonical_path:
        canon_url = url_for('category',
                            template=record.canonical_path,
                            _external=True,
                            **request.args)
    else:
        canon_url = url_for('entry',
                            entry_id=record.id,
                            category=record.category,
                            slug_text=record.slug_text if record.slug_text else None,
                            _external=True,
                            **request.args)

    LOGGER.debug("request.url=%s canon_url=%s", request.url, canon_url)

    if request.url != canon_url:
        # This could still be a redirected path...
        result = handle_path_alias()
        if result:
            return result

        # Redirect to the canonical URL
        return redirect(canon_url, code=301)

    return None


@orm.db_session(retry=5)
def render_entry(entry_id, slug_text='', category=''):
    """ Render an entry page.

    Arguments:

    entry_id -- The numeric ID of the entry to render
    slug_text -- The expected URL slug text
    category -- The expected category
    """

    # pylint: disable=too-many-return-statements,too-many-branches,unused-argument

    # check if it's a valid entry
    try:
        record = model.Entry.get(id=entry_id)
    except ValueError as error:
        raise http_error.BadRequest("Invalid entry ID") from error

    # see if the file still exists
    if record and not os.path.isfile(record.file_path):
        entry_expire_record(record)
        record = None

    if not record:
        # It's not a valid entry, so see if it's a redirection
        result = handle_path_alias()
        if result:
            return result

        LOGGER.info("Attempted to retrieve nonexistent entry %d", entry_id)
        raise http_error.NotFound("No such entry")

    return render_entry_record(record, category, None)


STATUS_EXCEPTIONS = {
    # Draft entries are a 403 with a custom error
    model.PublishStatus.DRAFT.value: http_error.Forbidden("Entry not available"),

    model.PublishStatus.GONE.value: http_error.Gone(),
    model.PublishStatus.ILLEGAL.value: http_error.UnavailableForLegalReasons(),
    model.PublishStatus.TEAPOT.value: http_error.ImATeapot(),
}


def render_entry_record(record: model.Entry, category: str, template: typing.Optional[str],
                        _mounted=False):
    """ Render an entry object """

    if record.status in STATUS_EXCEPTIONS:
        raise STATUS_EXCEPTIONS[record.status]

    # If the entry is private and the user isn't logged in, redirect
    result = _check_authorization(record, category)
    if result:
        return result

    # if the entry canonically redirects, do that now
    if record.redirect_url:
        LOGGER.debug("Redirecting to %s", record.redirect_url)
        return redirect(record.redirect_url, code=301)

    # check if the canonical URL matches
    if not _mounted:
        result = _check_canon_entry_url(record)
        if result:
            return result

    # Get the viewable entry
    entry_obj = Entry.load(record)

    # does the entry-id header mismatch? If so the old one is invalid
    try:
        current_id: typing.Optional[int] = int(entry_obj.get('Entry-ID'))  # type:ignore
    except (KeyError, TypeError, ValueError) as err:
        LOGGER.debug("Error checking entry ID: %s", err)
        current_id = record.id
    if current_id != record.id:
        LOGGER.debug("entry %s says it has id %d, index says %d",
                     entry_obj.file_path, current_id, record.id)

        from .entry import scan_file
        scan_file(entry_obj.file_path, None, True)

        return redirect(url_for('entry', entry_id=current_id))

    entry_template = (template
                      or entry_obj.get('Entry-Template')
                      or Category.load(category).get('Entry-Template')
                      or 'entry')

    tmpl = map_template(category, entry_template)
    if not tmpl:
        raise http_error.BadRequest("Missing entry template" + entry_template)

    rendered, etag = render_publ_template(
        tmpl,
        entry=entry_obj,
        category=Category.load(category))

    if request.if_none_match.contains(etag):
        return 'Not modified', 304

    headers = {
        'Content-Type': entry_obj.get('Content-Type', mime_type(tmpl)),
        'ETag': etag
    }

    return rendered, headers


@orm.db_session(retry=5)
def admin_dashboard(by=None):  # pylint:disable=invalid-name
    """ Render the authentication dashboard """
    cur_user = user.get_active()
    if not cur_user or not cur_user.is_admin:
        return handle_unauthorized(cur_user)

    tmpl = map_template('', '_admin')

    days = int(request.args.get('days', 7))
    count = int(request.args.get('count', 50))
    offset = int(request.args.get('offset', 0))

    log, remain = user.auth_log(start=offset, count=count)

    if 'user' in request.args:
        focus_user = user.User(request.args['user'])
    else:
        focus_user = None

    rendered, _ = render_publ_template(
        tmpl,
        users=user.known_users(days=days),
        log=log,
        count=count,
        offset=offset,
        days=days,
        remain=remain,
        by=by,
        focus_user=focus_user,
    )
    return rendered


def render_transparent_chit():
    """ Render a transparent chit for external, sized images """

    LOGGER.debug("chit")

    if request.if_none_match.contains('chit') or request.if_modified_since:
        return 'Not modified', 304

    out_bytes = base64.b64decode(
        "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")
    return out_bytes, {'Content-Type': 'image/gif', 'ETag': 'chit',
                       'Last-Modified': 'Tue, 31 Jul 1990 08:00:00 -0000'}


@orm.db_session
def retrieve_asset(filename):
    """ Retrieves a non-image asset associated with an entry """

    record = model.Image.get(asset_name=filename)
    if not record:
        raise http_error.NotFound("File not found")
    if not record.is_asset:
        raise http_error.Forbidden()

    return send_file(record.file_path, conditional=True)
