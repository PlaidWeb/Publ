# rendering.py
# Render and route functions

import os
from flask import request, redirect, render_template, send_from_directory, url_for
from . import path_alias, entry, model

import config

def map_template(orig_path, template_list):
    if type(template_list) == str:
        template_list = [template_list]

    for template in template_list:
        path = os.path.normpath(orig_path)
        while path != None:
            for extension in ['', '.html', '.xml', '.json']:
                candidate = os.path.join(path, template + extension)
                # app.logger.debug("Checking candidate %s", candidate)
                if os.path.isfile(os.path.join(config.template_directory, candidate)):
                    return candidate
            parent = os.path.dirname(path)
            if parent != path:
                path = parent
            else:
                path = None

def get_redirect():
    return path_alias.get_redirect([request.full_path, request.path])

def render_error(category, error_code):
    # TODO do we want to be able to do proper fallbacks here? (e.g. 410 -> 404)
    template = map_template(category, [str(error_code), 'error'])
    if template:
        return render_template(template, error=error_code), error_code
    # no template found, so fall back to default Flask handler
    flask.abort(error_code)

def render_category(category='', template='index'):
    # See if this is an aliased path
    redir = get_redirect()
    if redir:
        return redirect(redir)

    tmpl = map_template(category, template)
    return 'render template {} for category {}'.format(tmpl, category)

def render_entry(entry_id, slug_text='', category=''):
    # check if it's a valid entry
    record = model.Entry.get_or_none(model.Entry.id == entry_id)
    if not record:
        # This might be a legacy URL that tripped the id match rule
        redir = get_redirect()
        if redir:
            return redirect(redir)

        app.logger.info("Attempted to retrieve nonexistent entry %d", entry_id)
        return render_error(category, 404)

    # see if the file still exists
    if not os.path.isfile(record.file_path):
        # This entry no longer exists so delete it, and anything that references it
        # SQLite doesn't support cascading deletes so let's just clean up manually
        model.PathAlias.delete(model.PathAlias.redirect_entry == record).execute()
        record.delete_instance(recursive=True)
        return render_error(category, 410)

    # check if the canonical URL matches
    if record.category != category or record.slug_text != slug_text:
        return redirect(url_for('entry',
            entry_id=entry_id,
            category=record.category,
            slug_text=record.slug_text))

    if record.status == model.PublishStatus.DRAFT:
        return render_error(category, 403)

    tmpl = map_template(category, 'entry')
    entry_obj = entry.Entry(record)

    redir = entry_obj.get('Redirect-To')
    if redir:
        return redirect(redir)

    return render_template(tmpl, entry=entry_obj)

