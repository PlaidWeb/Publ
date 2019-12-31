# path_alias.py
""" Handling for URL aliases """

import typing

from flask import current_app, redirect, url_for
from pony import orm

from . import model, utils


@orm.db_session
def set_alias(alias: str, **kwargs) -> model.PathAlias:
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

    record = model.PathAlias.get(path=path)
    if record:
        record.set(**values)
    else:
        record = model.PathAlias(**values)

    orm.commit()
    return record


@orm.db_session
def remove_alias(path: str):
    """ Remove a path alias.

    Arguments:

    path -- the path to remove the alias of
    """
    orm.delete(p for p in model.PathAlias if p.path == path)  # type:ignore
    orm.commit()


@orm.db_session
def remove_aliases(target: typing.Union[model.Entry, model.Category]):
    """ Remove all aliases to a destination """

    if isinstance(target, model.Entry):
        orm.delete(p for p in model.PathAlias  # type:ignore
                   if p.entry == target)
    elif isinstance(target, model.Category):
        orm.delete(p for p in model.PathAlias  # type:ignore
                   if p.category == target)
    else:
        raise TypeError("Unknown type {}".format(type(target)))
    orm.commit()


def get_alias(path: str) -> typing.Tuple[typing.Optional[str], bool]:
    """ Get a path alias for a single path

    Returns a tuple of (url,is_permanent)
    """
    # pylint:disable=too-many-return-statements

    record = model.PathAlias.get(path=path)

    if not record:
        return None, False

    template = record.template if record.template != 'index' else None

    if record.entry and record.entry.visible:
        if record.template:
            # a template was requested, so we go to the category page
            category = (record.category.category
                        if record.category else record.entry.category)
            return url_for('category',
                           start=record.entry.id,
                           template=template,
                           category=category), True

        from . import entry  # pylint:disable=cyclic-import
        outbound = entry.Entry(record.entry).get('Redirect-To')
        if outbound:
            # The entry has a Redirect-To (soft redirect) header
            return outbound, False

        return url_for('entry',
                       entry_id=record.entry.id,
                       category=record.entry.category,
                       slug_text=record.entry.slug_text), True

    if record.category:
        return url_for('category',
                       category=record.category.category,
                       template=template), True

    if record.url:
        # This is an outbound URL that might be changed by the user, so
        # we don't do a 301 Permanently moved
        return record.url, False

    return None, False


def get_redirect(paths: typing.Union[str, typing.List[str]]):
    """ Get a redirect from a path or list of paths

    Arguments:

    paths -- either a single path string, or a list of paths to check

    Returns: a flask.redirect() result
    """
    for path in utils.as_list(paths):
        url, permanent = get_alias(path)
        if url:
            return redirect(url, 301 if permanent else 302)

        # pylint:disable=protected-access
        url, permanent = current_app._test_path_regex(path)
        if url:
            return redirect(url, 301 if permanent else 302)

    return None
