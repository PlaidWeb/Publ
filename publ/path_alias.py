# path_alias.py
""" Handling for URL aliases """

from __future__ import absolute_import, with_statement

from flask import url_for

from . import model


def set_alias(path, entry=None, url=None):
    """ Set a path alias.

    Arguments:

    path -- The path to alias
    entry -- The entry to alias it to
    url -- The external URL to alias it to
    """

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


def remove_alias(path):
    """ Remove a path alias.

    Arguments:

    path -- the path to remove the alias of
    """
    model.PathAlias.delete().where(model.PathAlias.path == path).execute()


def get_redirect(paths):
    """ Get a redirect from a path or list of paths

    Arguments:

    paths -- either a single path string, or a list of paths to check
    """

    if isinstance(paths, str):
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
    return None
