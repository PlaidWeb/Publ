# rendering.py
""" Rendering functions """

import os
import logging
import base64

import flask
from flask import request, redirect, render_template, url_for
import werkzeug.exceptions as http_error
from pony import orm

from . import config
from . import path_alias
from . import model
from . import image
from . import index
from .entry import Entry, expire_record
from .category import Category
from .template import Template
from . import view
from . import caching
from .caching import cache

LOGGER = logging.getLogger(__name__)  # pylint: disable=invalid-name

# mapping from template extension to MIME type; probably could be better
EXTENSION_MAP = {
    '.html': 'text/html; charset=utf-8',
    '.xml': 'application/xml',
    '.json': 'application/json',
    '.css': 'text/css',
    '.txt': 'text/plain'
}


def mime_type(template):
    """ infer the content-type from the extension """
    _, ext = os.path.splitext(template.filename)
    return EXTENSION_MAP.get(ext, 'text/html; charset=utf-8')


@cache.memoize()
def map_template(category, template_list):
    """
    Given a file path and an acceptable list of templates, return the
    best-matching template's path relative to the configured template
    directory.

    Arguments:

    category -- The path to map
    template_list -- A template to look up (as a string), or a list of templates.
    """

    if isinstance(template_list, str):
        template_list = [template_list]

    for template in template_list:
        path = os.path.normpath(category)
        while path is not None:
            for extension in ['', '.html', '.htm', '.xml', '.json']:
                candidate = os.path.join(path, template + extension)
                file_path = os.path.join(config.template_folder, candidate)
                if os.path.isfile(file_path):
                    return Template(template, candidate, file_path)
            parent = os.path.dirname(path)
            if parent != path:
                path = parent
            else:
                path = None


def get_template(template, relation):
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


def image_function(template=None, entry=None, category=None):
    """ Get a function that gets an image """

    path = []

    if entry is not None:
        path += entry.search_path
    if category is not None:
        # Since the category might be different than the entry's category we add
        # this too
        path += category.search_path
    if template is not None:
        path.append(os.path.join(
            config.content_folder,
            os.path.dirname(template.filename)))

    return lambda filename: image.get_image(filename, path)


@cache.memoize(unless=caching.do_not_cache)
def render_publ_template(template, **kwargs):
    """ Render out a template, providing the image function based on the args.

    Returns tuple of (rendered text, etag)
    """
    text = render_template(
        template.filename,
        template=template,
        image=image_function(
            template=template,
            category=kwargs.get('category'),
            entry=kwargs.get('entry')),
        **kwargs
    )

    return text, caching.get_etag(text)


@orm.db_session(retry=5)
def render_error(category, error_message, error_codes, exception=None):
    """ Render an error page.

    Arguments:

    category -- The category of the request
    error_message -- The message to provide to the error template
    error_codes -- The applicable HTTP error code(s). Will usually be an
        integer or a list of integers; the HTTP error response will always
        be the first error code in the list, and the others are alternates
        for looking up the error template to use.
    exception -- Any exception that led to this error page
    """

    LOGGER.info("Rendering error: category=%s error_message='%s' error_codes=%s exception=%s",
                category,
                error_message,
                error_codes,
                exception)

    if isinstance(error_codes, int):
        error_codes = [error_codes]

    error_code = error_codes[0]
    template_list = [str(code) for code in error_codes]
    template_list.append(str(int(error_code / 100) * 100))
    template_list.append('error')

    template = map_template(category, template_list)
    if template:
        return render_publ_template(
            template,
            _url_root=request.url_root,
            category=Category(category),
            error={'code': error_code, 'message': error_message},
            exception=exception)[0], error_code

    # no template found, so fall back to a default
    if exception and 'str' in exception:
        message = exception['str']
    else:
        message = "An unknown error occurred"
    return """<!DOCTYPE html>
<html>
<head><title>{code} {error}</title></head>
<body>
<h1>{error}</h1>
<p>{message}</p>
<hr><address><a href="http://publ.beesbuzz.biz">Publ</a> at {url}</address>
</body></html>""".format(code=error_code,
                         error=error_message,
                         message=message,
                         url=request.url), error_code


def render_exception(error):
    """ Catch-all renderer for the top-level exception handler """

    # Effectively strip off the leading '/', and let map_template decide
    # what the actual category is
    _, _, category = request.path.partition('/')

    qsize = index.queue_length()
    if isinstance(error, http_error.NotFound) and qsize:
        response = flask.make_response(render_error(
            category,
            "Site reindex in progress",
            503,
            {
                'type': 'Service Unavailable',
                'str': "The site's contents are not fully known; please try again later",
                'qsize': qsize
            }))
        response.headers['Retry-After'] = qsize
        response.headers['Refresh'] = max(5, qsize / 5)
        return response, 503

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
    if template and template.startswith('_'):
        raise http_error.Forbidden("Template is private")
    if template in ['entry', 'error']:
        raise http_error.BadRequest("Invalid view requested")

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
        _url_root=request.url_root,
        category=Category(category),
        view=view_obj)

    if request.if_none_match.contains(etag):
        return 'Not modified', 304

    return rendered, {'Content-Type': mime_type(tmpl),
                      'ETag': etag}


@orm.db_session(retry=5)
def render_entry(entry_id, slug_text='', category=''):
    """ Render an entry page.

    Arguments:

    entry_id -- The numeric ID of the entry to render
    slug_text -- The expected URL slug text
    category -- The expected category
    """

    # pylint: disable=too-many-return-statements

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

    # check if the canonical URL matches
    if record.category != category or record.slug_text != slug_text:
        # This could still be a redirected path...
        path_redirect = get_redirect()
        if path_redirect:
            return path_redirect

        # Redirect to the canonical URL
        return redirect(url_for('entry',
                                entry_id=entry_id,
                                category=record.category,
                                slug_text=record.slug_text if record.slug_text else None))

    # if the entry canonically redirects, do that now
    entry_redirect = record.redirect_url
    if entry_redirect:
        return redirect(entry_redirect)

    entry_template = (record.entry_template
                      or Category(category).get('Entry-Template')
                      or 'entry')

    tmpl = map_template(category, entry_template)
    if not tmpl:
        raise http_error.BadRequest("Missing entry template")

    # Get the viewable entry
    entry_obj = Entry(record)

    # does the entry-id header mismatch? If so the old one is invalid
    if int(entry_obj.get('Entry-ID')) != record.id:
        expire_record(record)
        return redirect(url_for('entry', entry_id=int(entry_obj.get('Entry-Id'))))

    rendered, etag = render_publ_template(
        tmpl,
        _url_root=request.url_root,
        entry=entry_obj,
        category=Category(category))

    if request.if_none_match.contains(etag):
        return 'Not modified', 304

    return rendered, {'Content-Type': mime_type(tmpl),
                      'ETag': etag}


def render_transparent_chit():
    """ Render a transparent chit for external, sized images """

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

    return flask.send_file(record.file_path, conditional=True)
