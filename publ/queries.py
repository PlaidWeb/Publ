# queries.py
""" Collection of commonly-used queries """

from enum import Enum

import arrow
from pony import orm

from . import model, utils


class InvalidQueryError(RuntimeError):
    """ An exception to raise if a query is invalid """


class FilterCombiner(Enum):
    """ Which operation to use when combining multiple operations in a filter """
    ANY = 0     # any of the criteria are present
    OR = 0      # synonym for ANY

    ALL = 1     # all of the criteria are present
    AND = 1     # synonym for ALL

    NONE = 2    # none of the criteria are present
    NOT = 2     # synonym for NONE


# Ordering queries for different sort orders
ORDER_BY = {
    'newest': (orm.desc(model.Entry.local_date), orm.desc(model.Entry.id)),
    'oldest': (model.Entry.local_date, model.Entry.id),
    'title': (model.Entry.sort_title, model.Entry.id)
}

REVERSE_ORDER_BY = {
    'newest': (model.Entry.local_date, model.Entry.id),
    'oldest': (orm.desc(model.Entry.local_date), orm.desc(model.Entry.id)),
    'title': (orm.desc(model.Entry.sort_title), orm.desc(model.Entry.id))
}


def where_entry_visible(query, timestamp=None):
    """ Generate a where clause for currently-visible entries

    Arguments:

    date -- The date to generate it relative to (defaults to right now)
    """

    ref_time = arrow.utcnow().float_timestamp if timestamp is None else timestamp

    return query.filter(lambda e:
                        e.status == model.PublishStatus.PUBLISHED.value or (
                            e.status == model.PublishStatus.SCHEDULED.value and (
                                e.utc_timestamp <= ref_time)
                        ))


def where_entry_visible_future(query):
    """ Generate a where clause for entries that are visible now or in the future """

    return query.filter(lambda e:
                        e.status in (model.PublishStatus.PUBLISHED.value,
                                     model.PublishStatus.SCHEDULED.value))


def where_entry_deleted(query):
    """ Generate a where clause for entries that have been deleted """
    return query.filter(lambda e:
                        e.status == model.PublishStatus.GONE.value)


def where_entry_category(query, category, recurse=False):
    """ Generate a where clause for a particular category """

    if utils.is_list(category):
        clist = {str(c) for c in category}

        if recurse:
            prefixes = tuple(c + '/' for c in clist)
            categories = orm.select(e.category for e in model.Entry)
            allowed = {*clist, *[c for c in categories if c.startswith(prefixes)]}
            return query.filter(lambda e: e.category in allowed)

        return query.filter(lambda e: e.category in clist)

    category = str(category)
    if category and recurse:
        # We're recursing and aren't in /, so add the prefix clause
        return query.filter(lambda e:
                            e.category == category or
                            e.category.startswith(category + '/'))

    if not recurse:
        # We're not recursing, so we need an exact match on a possibly-empty
        # category
        return query.filter(lambda e: e.category == category)

    # We're recursing and have no category, which means we're doing nothing
    return query


def where_entry_category_not(query, category):
    """ Generate a where clause for not being in a particular category """
    if utils.is_list(category):
        clist = [str(c) for c in category]
        return query.filter(lambda e: e.category not in clist)
    return query.filter(lambda e: e.category != str(category))


def where_before_entry(query, ref):
    """ Generate a where clause for prior entries

    ref -- The entry of reference
    """
    if not ref:
        raise InvalidQueryError("Attempted to reference non-existent entry")
    return query.filter(lambda e: (e.local_date, e.id) < (ref.local_date, ref.id))


def where_after_entry(query, ref):
    """ Generate a where clause for later entries

    ref -- the entry of reference
    """
    if not ref:
        raise InvalidQueryError("Attempted to reference non-existent entry")
    return query.filter(lambda e: (e.local_date, e.id) > (ref.local_date, ref.id))


def where_entry_last(query, ref):
    """ Generate a where clause where this is the last entry

    ref -- the entry of reference
    """
    if not ref:
        raise InvalidQueryError("Attempted to reference non-existent entry")
    # return query.filter(lambda e: (e.local_date, e.id) <= (ref.local_date, ref.id))
    # workaround for https://github.com/ponyorm/pony/issues/579
    return query.filter(lambda e: e.local_date < ref.local_date or
                        (e.local_date == ref.local_date and e.id <= ref.id))


def where_entry_first(query, ref):
    """ Generate a where clause where this is the first entry

    ref -- the entry of reference
    """
    if not ref:
        raise InvalidQueryError("Attempted to reference non-existent entry")
    # return query.filter(lambda e: (e.local_date, e.id) >= (ref.local_date, ref.id))
    # workaround for https://github.com/ponyorm/pony/issues/579
    return query.filter(lambda e: e.local_date > ref.local_date or
                        (e.local_date == ref.local_date and e.id >= ref.id))


def where_entry_type(query, entry_type):
    """ Generate a where clause for entries of certain types

    entry_type -- one or more entries to check against
    """
    if utils.is_list(entry_type):
        return query.filter(lambda e: e.entry_type in entry_type)
    return query.filter(lambda e: e.entry_type == entry_type)


def where_entry_type_not(query, entry_type):
    """ Generate a where clause for entries that aren't of certain types

    entry_type -- one or more entries to check against
    """
    if utils.is_list(entry_type):
        return query.filter(lambda e: e.entry_type not in entry_type)
    return query.filter(lambda e: e.entry_type != entry_type)


def where_entry_tag(query, tags, operation: FilterCombiner):
    """ Generate a where clause for entries with the given tags """
    tags = [utils.tag_key(t) for t in utils.as_list(tags)]

    if operation == FilterCombiner.ANY:
        return query.filter(lambda e: orm.exists(t for t in e.tags
                                                 if t.tag.key in tags))

    if operation == FilterCombiner.ALL:
        for tag in tags:
            # pylint:disable=undefined-loop-variable,cell-var-from-loop
            query = query.filter(lambda e: orm.exists(t for t in e.tags
                                                      if t.tag.key == tag))
        return query

    if operation == FilterCombiner.NONE:
        for tag in tags:
            # pylint:disable=cell-var-from-loop
            query = query.filter(lambda e: not orm.exists(t for t in e.tags
                                                          if t.tag.key == tag))
        return query

    raise InvalidQueryError("Unsupported FilterCombiner " + str(operation))


def where_entry_date(query, datespec):
    """ Where clause for entries which match a textual date spec

    datespec -- The date spec to check for, in YYYY[[-]MM[[-]DD]] format
    """
    try:
        date, interval, _ = utils.parse_date(datespec)
    except ValueError as error:
        raise InvalidQueryError(f"Invalid date {datespec}") from error
    start_date, end_date = date.span(interval)

    return query.filter(lambda e:
                        e.local_date >= start_date.naive and
                        e.local_date <= end_date.naive
                        )


def where_entry_attachments(query, entry):
    """ Where clause for entries which are attachments of the specified one. """
    return query.filter(lambda e: e in entry.attachments)


def where_entry_attached(query, entry):
    """ Where clause for entries which this one is attached onto. """
    return query.filter(lambda e: e in entry.attached)


def where_entry_has_attachments(query, val):
    """ Where clause for entries which have attachments """
    return query.filter(lambda e: val == orm.exists(e.attachments))


def where_entry_is_attached(query, val):
    """ Where clause for entries which are attached """
    return query.filter(lambda e: val == orm.exists(e.attached))


def get_entry(entry):
    """ Helper function to get an entry by ID or by object """

    if isinstance(entry, model.Entry):
        return entry

    if hasattr(entry, '_record'):
        return getattr(entry, '_record')

    if isinstance(entry, (int, str)):
        try:
            return model.Entry.get(id=int(entry))
        except ValueError as error:
            raise InvalidQueryError(f"Invalid entry ID {entry}") from error

    raise InvalidQueryError(f"entry is of unknown type {type(entry)}")


def build_query(spec):
    """ build the where clause based on a view specification

    spec -- The view specification. Contains the following possible values:
        future -- Boolean; whether to include entries from the future
        category -- Which category to limit to
        recurse -- Whether to include subcategories
        entry_type -- one or more entry types to include
        entry_type_not -- one or more entry types to exclude
        date -- a date spec
        last -- the last entry to end a view on
        first -- the first entry to start a view on
        before -- get entries from before this one
        after -- get entries from after this one
    """
    # pylint:disable=too-many-branches

    query = model.Entry.select()

    # primarily restrict by publication status
    if spec.get('_all', False):
        pass
    elif spec.get('_deleted', False):
        query = where_entry_deleted(query)
    else:
        if spec.get('future', False):
            query = where_entry_visible_future(query)
        else:
            query = where_entry_visible(query)

    # restrict by category
    if spec.get('category') is not None:
        recurse = spec.get('recurse', False)
        query = where_entry_category(query, spec.get('category', ''), recurse)

    if spec.get('category_not') is not None:
        query = where_entry_category_not(query, spec.get('category_not'))

    if spec.get('entry_type') is not None:
        query = where_entry_type(query, spec['entry_type'])

    if spec.get('entry_type_not') is not None:
        query = where_entry_type_not(query, spec['entry_type_not'])

    if spec.get('tag') is not None:
        query = where_entry_tag(query, spec['tag'],
                                FilterCombiner[spec.get('tag_filter', 'ANY').upper()])

    if spec.get('date') is not None:
        query = where_entry_date(query, spec['date'])

    if spec.get('last') is not None:
        query = where_entry_last(query, get_entry(spec['last']))

    if spec.get('first') is not None:
        query = where_entry_first(query, get_entry(spec['first']))

    if spec.get('before') is not None:
        query = where_before_entry(query, get_entry(spec['before']))

    if spec.get('after') is not None:
        query = where_after_entry(query, get_entry(spec['after']))

    if spec.get('attachments') is not None:
        query = where_entry_attachments(query, get_entry(spec['attachments']))

    if spec.get('attached') is not None:
        query = where_entry_attached(query, get_entry(spec['attached']))

    if spec.get('has_attachments') is not None:
        query = where_entry_has_attachments(query, spec['has_attachments'])

    if spec.get('is_attached') is not None:
        query = where_entry_is_attached(query, spec['is_attached'])

    return query.distinct()
