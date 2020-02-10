# rendering.py
""" Rendering functions """

import base64
import logging
import os
import typing

import flask
import werkzeug.exceptions as http_error
from flask import redirect, request, send_file, url_for
from pony import orm

from . import (caching, config, image, index, model, path_alias, queries, user,
               utils, view)
from .caching import cache
from .category import Category
from .entry import Entry, expire_record
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


def get_redirect():
    """ Check to see if the current request is a redirection """
    alias = path_alias.get_redirect(request.path)
    if alias:
        return alias

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
        path += os.path.join(config.content_folder,
                             os.path.dirname(template.filename)),

    return lambda filename: image.get_image(filename, path)


def render_publ_template(template: Template, **kwargs) -> typing.Tuple[str, str]:
    """ Render out a template, providing the image function based on the args.

    Returns tuple of (rendered text, etag)
    """
    @cache.memoize(unless=caching.do_not_cache)
    def do_render(template: Template, **kwargs) -> typing.Tuple[str, str]:
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
        return text, caching.get_etag(text)

    try:
        return do_render(template,
                         user=user.get_active(),
                         _url=request.url,
                         _index_time=index.last_modified(),
                         **kwargs)
    except queries.InvalidQueryError as err:
        raise http_error.BadRequest(str(err))


@orm.db_session(retry=5)
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
            category=Category(category),
            error={'code': error_code, 'message': error_message},
            exception=exception)[0], error_code, headers

    return '%d %s' % (error_code, error_message), error_code, headers


def render_exception(error):
    """ Catch-all renderer for the top-level exception handler """

    LOGGER.debug("render_exception %s %s", type(error), error)

    # Effectively strip off the leading '/', so map_template can decide
    # what the actual category is
    category = request.path[1:]

    qsize = index.queue_length()
    if isinstance(error, http_error.NotFound) and qsize:
        retry = max(5, qsize / 5)
        return render_error(
            category, "Site reindex in progress", 503,
            exception={
                'type': 'Service Unavailable',
                'str': "The site's contents are not fully known; please try again later",
                'qsize': qsize
            },
            headers={
                **NO_CACHE,
                'Retry-After': retry,
                'Refresh': retry
            })

    if isinstance(error, http_error.Unauthorized):
        from flask import current_app as app

        force_ssl = config.auth.get('AUTH_FORCE_HTTPS')
        if force_ssl and request.scheme != 'https':
            return redirect(utils.secure_link(request.endpoint,
                                              **request.view_args,
                                              **request.args))

        flask.g.needs_token = True
        if 'token_error' in flask.g:
            flask.flash(flask.g.token_error)
        return app.authl.render_login_form(destination=utils.redir_path()), 401

    if isinstance(error, http_error.HTTPException):
        return render_error(category, error.name, error.code, exception={
            'type': type(error).__name__,
            'str': error.description,
            'args': error.args
        })

    return render_error(category, "Exception occurred", 500, exception={
        'type': type(error).__name__,
        'str': str(error),
        'args': error.args
    })


@orm.db_session(retry=5)
def render_path_alias(path):
    """ Render a known path-alias (used primarily for forced .php redirects) """

    redir = path_alias.get_redirect('/' + path)
    if not redir:
        raise http_error.NotFound("Path redirection not found")
    return redir


@orm.db_session(retry=5)
def render_category(category='', template=None):
    """ Render a category page.

    Arguments:

    category -- The category to render
    template -- The template to render it with
    """
    # pylint:disable=too-many-return-statements

    # See if this is an aliased path
    redir = get_redirect()
    if redir:
        return redir

    # Forbidden template types
    if template in ['entry', 'error', 'login', 'unauthorized', 'logout']:
        LOGGER.info("Attempted to render special template %s", template)
        raise http_error.Forbidden("Invalid view requested")

    if category:
        # See if there's any entries for the view...
        if not orm.select(e for e in model.Entry if e.category == category or
                          e.category.startswith(category + '/')):
            raise http_error.NotFound("No such category")

    if not template:
        template = Category(category).get('Index-Template') or 'index'

    tmpl = map_template(category, template)

    if not tmpl:
        # this might actually be a malformed category URL
        test_path = '/'.join((category, template)) if category else template
        LOGGER.debug("Checking for malformed category %s", test_path)
        record = orm.select(
            e for e in model.Entry if e.category == test_path).exists()
        if record:
            return redirect(url_for('category', category=test_path, **request.args))

        # nope, we just don't know what this is
        raise http_error.NotFound(
            "No such view '{template}'".format(template=template))

    view_spec = view.parse_view_spec(request.args)
    view_spec['category'] = category
    view_obj = view.View(view_spec)

    rendered, etag = render_publ_template(
        tmpl,
        category=Category(category),
        view=view_obj)

    if request.if_none_match.contains(etag):
        return 'Not modified', 304

    return rendered, {'Content-Type': mime_type(tmpl),
                      'ETag': etag}


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
            raise http_error.Forbidden(
                "User {name} does not have access".format(name=cur_user.name))

        # Render the category's unauthorized template
        return render_publ_template(tmpl, category=Category(category), **kwargs)[0], 403, NO_CACHE

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
                                       entry=Entry(record),
                                       category=category)
    return None


def _check_canon_entry_url(record):
    """ Check to see if an entry is being requested at its canonical URL """
    canon_url = url_for('entry',
                        entry_id=record.id,
                        category=record.category,
                        slug_text=record.slug_text if record.slug_text else None,
                        _external=True,
                        **request.args)

    LOGGER.debug("request.url=%s canon_url=%s", request.url, canon_url)

    if request.url != canon_url:
        # This could still be a redirected path...
        path_redirect = get_redirect()
        if path_redirect:
            return path_redirect

        # Redirect to the canonical URL
        return redirect(canon_url)

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
    record = model.Entry.get(id=entry_id)
    if not record:
        # It's not a valid entry, so see if it's a redirection
        path_redirect = get_redirect()
        if path_redirect:
            return path_redirect

        LOGGER.info("Attempted to retrieve nonexistent entry %d", entry_id)
        raise http_error.NotFound("No such entry")

    # see if the file still exists
    if not os.path.isfile(record.file_path):
        expire_record(record)

        # See if there's a redirection
        path_redirect = get_redirect()
        if path_redirect:
            return path_redirect

        raise http_error.NotFound("No such entry")

    # Show an access denied error if the entry has been set to draft mode
    if record.status == model.PublishStatus.DRAFT.value:
        raise http_error.Forbidden("Entry not available")
    # Show a gone error if the entry has been deleted
    if record.status == model.PublishStatus.GONE.value:
        raise http_error.Gone()

    # If the entry is private and the user isn't logged in, redirect
    result = _check_authorization(record, category)
    if result:
        return result

    # check if the canonical URL matches
    result = _check_canon_entry_url(record)
    if result:
        return result

    # if the entry canonically redirects, do that now
    if record.redirect_url:
        return redirect(record.redirect_url)

    # Get the viewable entry
    entry_obj = Entry(record)

    # does the entry-id header mismatch? If so the old one is invalid
    try:
        current_id = int(entry_obj.get('Entry-ID'))
    except (KeyError, TypeError, ValueError) as err:
        LOGGER.debug("Error checking entry ID: %s", err)
        current_id = None
    if current_id != record.id:
        LOGGER.debug("entry %s says it has id %d, index says %d",
                     entry_obj.file_path, current_id, record.id)

        from .entry import scan_file
        scan_file(entry_obj.file_path, None, True)

        return redirect(url_for('entry', entry_id=entry_id))

    entry_template = (entry_obj.get('Entry-Template')
                      or Category(category).get('Entry-Template')
                      or 'entry')

    tmpl = map_template(category, entry_template)
    if not tmpl:
        raise http_error.BadRequest("Missing entry template" + entry_template)

    rendered, etag = render_publ_template(
        tmpl,
        entry=entry_obj,
        category=Category(category))

    if request.if_none_match.contains(etag):
        return 'Not modified', 304

    headers = {
        'Content-Type': entry_obj.get('Content-Type', mime_type(tmpl)),
        'ETag': etag
    }
    if record.status == model.PublishStatus.HIDDEN.value:
        headers = {**headers, **NO_CACHE}

    return rendered, headers


@orm.db_session(retry=5)
def admin_dashboard(by=None):  # pylint:disable=invalid-name
    """ Render the authentication dashboard """
    cur_user = user.get_active()
    if not cur_user or not cur_user.is_admin:
        return handle_unauthorized(cur_user)

    tmpl = map_template('', '_admin')

    days = int(request.args.get('days', 0))
    count = int(request.args.get('count', 50))
    offset = int(request.args.get('offset', 0))

    log, remain = user.auth_log(start=offset, count=count, days=days)

    rendered, _ = render_publ_template(
        tmpl,
        users=user.known_users(days=days),
        log=log,
        count=count,
        offset=offset,
        days=days,
        remain=remain,
        by=by
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


@orm.db_session(retry=5)
def retrieve_asset(filename):
    """ Retrieves a non-image asset associated with an entry """

    record = model.Image.get(asset_name=filename)
    if not record:
        raise http_error.NotFound("File not found")
    if not record.is_asset:
        raise http_error.Forbidden()

    return send_file(record.file_path, conditional=True)
