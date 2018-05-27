# path_alias.py
""" Handling for URL aliases """

from __future__ import absolute_import, with_statement

from flask import url_for, redirect

from . import model, entry


def set_alias(alias, **kwargs):
    """ Set a path alias.

    Arguments:

    alias -- The alias specification
    entry -- The entry to alias it to
    category -- The category to alias it to
    url -- The external URL to alias it to

    """

    spec = alias.split()
    path = spec[0]

    values = {**kwargs, 'path': path}

    if len(spec) > 1:
        values['template'] = spec[1]

    model.PathAlias.replace(**values).execute()


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

    Returns: a flask.redirect() result
    """

    if isinstance(paths, str):
        paths = [paths]

    for path in paths:
        record = model.PathAlias.get_or_none(model.PathAlias.path == path)

        if record:
            if record.template:
                # we want a specific template view

                template = record.template
                if template == 'index':
                    # map this back to the category default
                    template = None

                if record.entry:
                    category = (record.category.category
                                if record.category else record.entry.category)
                    return redirect(url_for('category',
                                            start=record.entry.id,
                                            template=template,
                                            category=category), code=301)

                if record.category:
                    return redirect(url_for('category',
                                            category=record.category.category,
                                            template=template), code=301)

            if record.entry:
                outbound = entry.Entry(record.entry).get('Redirect-To')
                if outbound:
                    # The referred entry has a soft Redirect-To, so let's go
                    # directly to it. We don't use a 301 because this is an
                    # outbound redirection that the user might change.
                    return redirect(outbound)
                return redirect(url_for('entry',
                                        entry_id=record.entry.id,
                                        category=record.entry.category,
                                        slug_text=record.entry.slug_text), code=301)

            if record.category:
                return redirect(url_for('category',
                                        category=record.category.category,
                                        template=record.template), code=301)

            if record.url:
                # This is an outbound URL that might be changed by the user, so
                # we don't do a 301 Permanently moved
                return redirect(record.url)

    return None
