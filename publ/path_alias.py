# path_alias.py
# Handling for URL aliases

from . import model
from flask import url_for

def set_alias(path, entry=None, url=None):
    if path[0] == '!':
        # We want to delete this redirection
        model.PathAlias.delete(model.PathAlias.path == path).execute()
        return

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

def get_redirect(paths):
    if type(paths) == str:
        paths = [paths]

    for path in paths:
        record = model.PathAlias.get_or_none(model.PathAlias.path == path)
        if record and record.redirect_entry:
            return url_for('entry',
                entry_id=record.redirect_entry.id,
                category=record.redirect_entry.category,
                slug_text=record.redirect_entry.slug_text)
        elif record and record.redirect_url:
            return record.redirect_url
