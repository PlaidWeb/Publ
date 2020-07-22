# path_alias.py
""" Handling for URL aliases """

import typing

from flask import current_app, redirect, url_for
from pony import orm

from . import model

# redirection types
PERMANENT = 301
TEMPORARY = 302


@orm.db_session
def set_alias(alias: str, alias_type: model.AliasType, **kwargs) -> model.PathAlias:
    """ Set a path alias.

    Arguments:

    alias -- The alias specification
    entry -- The entry to alias it to
    category -- The category to alias it to
    url -- The external URL to alias it to
    """

    spec = alias.split()
    path = spec[0]

    if not path or path[0] != '/':
        path = '/' + path

    values = {
        **kwargs,
        'path': path,
        'alias_type': alias_type.value
    }

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
        raise TypeError(f"Unknown type {type(target)}")
    orm.commit()


class Disposition:
    """ Alias disposition base class """
    # pylint:disable=too-few-public-methods

    def __init__(self):
        pass


class Response(Disposition):
    """ Disposition that provides a response directly """
    # pylint:disable=too-few-public-methods

    def __init__(self, response):
        super().__init__()
        self.response = response


class RenderEntry(Disposition):
    """ Disposition that requests an entry render """
    # pylint:disable=too-few-public-methods

    def __init__(self, entry: model.Entry, category: str, template: typing.Optional[str]):
        super().__init__()
        self.entry = entry
        self.category = category
        self.template = template


class RenderCategory(Disposition):
    """ Disposition that requests a category render """
    # pylint:disable=too-few-public-methods

    def __init__(self, category: str, template: typing.Optional[str]):
        super().__init__()
        self.category = category
        self.template = template


def get_alias(path: str) -> typing.Optional[Disposition]:
    """ Get a path's alias mapping """

    record = model.PathAlias.get(path=path)

    if not record or (record.entry and not record.entry.visible):
        url, permanent = current_app.test_path_regex(path)
        if url:
            return Response(redirect(url, PERMANENT if permanent else TEMPORARY))

        return None

    alias_type = model.AliasType(record.alias_type)

    if record.category:
        category = record.category.category
    elif record.entry:
        category = record.entry.category
    else:
        category = ''

    template_name = record.template if record.template != 'index' else None

    if alias_type == model.AliasType.REDIRECT:
        args = {'category': category} if category else {}

        if record.template or not record.entry:
            endpoint = 'category'
            if template_name:
                args['template'] = template_name
            if record.entry:
                args['id'] = record.entry.id
        else:
            if record.entry.redirect_url:
                return Response(redirect(record.entry.redirect_url, PERMANENT))
            endpoint = 'entry'
            args['entry_id'] = record.entry.id

        return Response(redirect(url_for(endpoint, **args), PERMANENT))

    if record.entry:
        return RenderEntry(record.entry, category, record.template)

    return RenderCategory(category, record.template)
