# rendering.py
""" Rendering functions """

from __future__ import absolute_import, with_statement

import os
import logging
import base64

import flask
from flask import request, redirect, render_template, url_for
from werkzeug.exceptions import HTTPException

from . import config
from . import path_alias
from . import model
from . import image
from .entry import Entry, expire_record
from .category import Category
from .template import Template
from .view import View
from . import caching
from .caching import cache

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name

# mapping from template extension to MIME type; probably could be better
EXTENSION_MAP = {
    '.html': 'text/html; charset=utf-8',
    '.xml': 'application/xml',
    '.json': 'application/json',
    '.css': 'text/css'
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
        while path != None:
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


def get_redirect():
    """ Check to see if the current request is a redirection """
    return path_alias.get_redirect([request.full_path, request.path])


def image_function(template=None, entry=None, category=None):
    """ Get a function that gets an image """

    path = []

    if entry is not None:
        path += entry.image_search_path
    if category is not None:
        # Since the category might be a parent of the entry's category we add
        # this too
        path += category.image_search_path
    if template is not None:
        path.append(os.path.join(
            config.content_folder,
            os.path.dirname(template.filename)))

    return lambda filename: image.get_image(filename, path)


def render_publ_template(template, **kwargs):
    """ Render out a template, providing the image function based on the args """
    return render_template(
        template.filename,
        template=template,
        image=image_function(
            template=template,
            category=kwargs.get('category'),
            entry=kwargs.get('entry')),
        **kwargs
    )


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

    if isinstance(error_codes, int):
        error_codes = [error_codes]

    error_code = error_codes[0]
    template_list = [str(code) for code in error_codes]
    template_list.append('error')

    template = map_template(category, template_list)
    if template:
        return render_publ_template(
            template,
            error={'code': error_code, 'message': error_message},
            exception=exception), error_code

    # no template found, so fall back to default Flask handler
    return flask.abort(error_code)


def render_exception(error):
    """ Catch-all renderer for the top-level exception handler """
    _, _, category = str.partition(request.path, '/')
    if isinstance(error, HTTPException) and error.code:
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


def render_path_alias(path):
    """ Render a known path-alias (used primarily for Dreamhost .php redirects) """

    redir = path_alias.get_redirect('/' + path)
    if not redir:
        return render_error('', 'Path redirection not found', 404)
    return redirect(redir)


@cache.cached(key_prefix=caching.make_category_key)
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
        return redirect(redir)

    # Forbidden template types
    if template and template.startswith('_'):
        return render_error(category, 'Access denied', 403)
    if template in ['entry', 'error']:
        return render_error(category, 'Unsupported template', 400)

    if category:
        # See if there's any entries for the view...
        if not model.Entry.get_or_none((model.Entry.category == category) |
                                       (model.Entry.category.startswith(category + '/'))):
            return render_error(category, 'No such category', 404)

    if not template:
        template = Category(category).get('Index-Template') or 'index'

    tmpl = map_template(category, template)

    if not tmpl:
       # this might actually be a malformed category URL
        test_path = os.path.join(category, template)
        record = model.Entry.get_or_none(model.Entry.category == test_path)
        if record:
            return redirect(url_for('category', category=test_path))

        # nope, we just don't know what this is
        return render_error(category, 'No such template', 404)

    view_spec = {'category': category}
    for key in ['date', 'start', 'last', 'first', 'before', 'after']:
        if key in request.args:
            view_spec[key] = request.args[key]

    view_obj = View(view_spec)
    return render_publ_template(
        tmpl,
        category=Category(category),
        view=view_obj), {'Content-Type': mime_type(tmpl)}


@cache.cached(key_prefix=caching.make_entry_key)
def render_entry(entry_id, slug_text='', category=''):
    """ Render an entry page.

    Arguments:

    entry_id -- The numeric ID of the entry to render
    slug_text -- The expected URL slug text
    category -- The expected category
    """

    # pylint: disable=too-many-return-statements

    # check if it's a valid entry
    record = model.Entry.get_or_none(model.Entry.id == entry_id)
    if not record:
        # It's not a valid entry, so see if it's a redirection
        path_redirect = get_redirect()
        if path_redirect:
            return redirect(path_redirect)

        logger.info("Attempted to retrieve nonexistent entry %d", entry_id)
        return render_error(category, 'Entry not found', 404)

    # see if the file still exists
    if not os.path.isfile(record.file_path):
        expire_record(record)

        # See if there's a redirection
        path_redirect = get_redirect()
        if path_redirect:
            return redirect(path_redirect)

        return render_error(category, 'Entry not found', 404)

    # Show an access denied error if the entry has been set to draft mode
    if record.status == model.PublishStatus.DRAFT:
        return render_error(category, 'Entry not available', 403)

    # read the entry from disk
    entry_obj = Entry(record)

    # does the entry-id header mismatch? If so the old one is invalid
    if int(entry_obj.get('Entry-ID')) != record.id:
        expire_record(record)
        return render_error(category, 'Entry not found', 404)

    # check if the canonical URL matches
    if record.category != category or record.slug_text != slug_text:
        # This could still be a redirected path...
        path_redirect = get_redirect()
        if path_redirect:
            return redirect(path_redirect)

        # Redirect to the canonical URL
        return redirect(url_for('entry',
                                entry_id=entry_id,
                                category=record.category,
                                slug_text=record.slug_text))

    # if the entry canonically redirects, do that now
    entry_redirect = entry_obj.get('Redirect-To')
    if entry_redirect:
        return redirect(entry_redirect)

    entry_template = (entry_obj.get('Entry-Template')
                      or Category(category).get('Entry-Template')
                      or 'entry')

    tmpl = map_template(category, entry_template)
    if not tmpl:
        return render_error(category, 'Entry template not found', 400)

    return render_publ_template(
        tmpl,
        entry=entry_obj,
        category=Category(category)), {'Content-Type': mime_type(tmpl)}


def render_transparent_chit():
    """ Render a transparent chit for external, sized images """
    out_bytes = base64.b64decode(
        "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")
    return out_bytes, {'Content-Type': 'image/gif'}
