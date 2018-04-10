# rendering.py
# Render and route functions

import os
import logging
from flask import request, redirect, render_template, send_from_directory, url_for, make_response
from . import path_alias, model
from .entry import Entry, expire_record
from .category import Category
from .template import Template
from .view import View

import config

logger = logging.getLogger(__name__)

# mapping from template extension to MIME type; probably could be better
extmap = {
    '.xml': 'application/xml',
    '.json': 'application/json'
}

def mimetype(template):
    # infer the content-type from the extension
    _,ext = os.path.splitext(template.filename)
    return extmap.get(ext, 'text/html; charset=utf-8')

def map_template(orig_path, template_list):
    if type(template_list) == str:
        template_list = [template_list]

    for template in template_list:
        path = os.path.normpath(orig_path)
        while path != None:
            for extension in ['', '.html', '.xml', '.json']:
                candidate = os.path.join(path, template + extension)
                file_path = os.path.join(config.template_directory, candidate)
                if os.path.isfile(file_path):
                    return Template(template, candidate, file_path)
            parent = os.path.dirname(path)
            if parent != path:
                path = parent
            else:
                path = None

def static_url(path, absolute=False):
    return url_for('static', filename=path, _external=absolute)

def get_redirect():
    return path_alias.get_redirect([request.full_path, request.path])

def render_error(category, error_message, *error_codes):
    error_code = error_codes[0]

    template_list = [str(code) for code in error_codes]
    template_list.append('error')

    template = map_template(category, template_list)
    if template:
        return render_template(
            template.filename,
            error={'code':error_code, 'message':error_message},
            template=template), error_code

    # no template found, so fall back to default Flask handler
    flask.abort(error_code)

def render_path_alias(path):
    redir = path_alias.get_redirect('/' + path)
    if not redir:
        return render_error('', 'Path redirection not found', 404)
    return redirect(redir)

def render_category(category='', template='index'):
    # See if this is an aliased path
    redir = get_redirect()
    if redir:
        return redirect(redir)

    # Forbidden template types
    if template in ['entry', 'error']:
        return render_error(category, 'Unsupported template', 400)

    if category:
        # See if there's any entries for the view...
        if not model.Entry.get_or_none((model.Entry.category == category) |
            (model.Entry.category.startswith(category + '/'))):
            return render_error(category, 'Category not found', 404)

    tmpl = map_template(category, template)

    if not tmpl:
       # this might actually be a malformed category URL
        test_path = os.path.join(category,template)
        record = model.Entry.get_or_none(model.Entry.category == test_path)
        if record:
            return redirect(url_for('category',category=test_path))

        # nope, we just don't know what this is
        return render_error(category, 'Template not found', 400)

    view_spec = {'category': category}
    for key in ['date', 'last', 'first', 'before', 'after']:
        if key in request.args:
            view_spec[key] = request.args[key]

    view_obj = View(view_spec)
    return render_template(tmpl.filename,
        category=Category(category),
        view=view_obj,
        template=tmpl), { 'Content-Type': mimetype(tmpl) }

def render_entry(entry_id, slug_text='', category=''):
    # check if it's a valid entry
    record = model.Entry.get_or_none(model.Entry.id == entry_id)
    if not record:
        # It's not a valid entry, so see if it's a redirection
        path_redirect = get_redirect()
        if path_redirect:
            return redirect(path_redir)

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

    tmpl = map_template(category, 'entry')
    if not tmpl:
        return render_error(category, 'Entry template not found', 400)

    return render_template(tmpl.filename,
        entry=entry_obj,
        category=Category(category),
        template=tmpl), { 'Content-Type': mimetype(tmpl) }

