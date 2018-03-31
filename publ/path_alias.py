# path_alias.py
# Handling for URL aliases

from . import model
from flask import url_for

def set_alias(path, entry=None, url=None):
    record, created = model.PathAlias.get_or_create(
        path=path,
        defaults={
            'redirect_entry': entry,
            'redirect_url': url
        })
    if not created:
        record.redirect_entry = entry
        record.redirect_url = url
        record.save()

def get_redirection(path):
    record = model.PathAlias.get_or_none(model.PathAlias.path == path)
    if not record:
        return None
    if record.redirect_entry:
        return url_for('render_entry',
            entry_id=record.redirect_entry.id,
            category=record.redirect_entry.category,
            slug_text=record.redirect_entry.slug_text)
    if record.redirect_url:
        return record.redirect_url
    return None
