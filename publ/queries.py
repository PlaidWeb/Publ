# queries.py
""" Collection of commonly-used queries """

import arrow
from pony import orm

from . import model, utils


def where_entry_visible(query, date=None):
    """ Generate a where clause for currently-visible entries

    Arguments:

    date -- The date to generate it relative to (defaults to right now)
    """

    return orm.select(
        e for e in query
        if e.status == model.PublishStatus.PUBLISHED.value or
        (e.status == model.PublishStatus.SCHEDULED.value and
         (e.utc_date <= (date or arrow.utcnow().datetime))
         )
    )


def where_entry_visible_future(query):
    """ Generate a where clause for entries that are visible now or in the future """

    return orm.select(
        e for e in query
        if e.status in (model.PublishStatus.PUBLISHED.value,
                        model.PublishStatus.SCHEDULED.value))


def where_entry_deleted(query):
    """ Generate a where clause for entries that have been deleted """
    return orm.select(
        e for e in query
        if e.status == model.PublishStatus.GONE.value)


def where_entry_category(query, category, recurse=False):
    """ Generate a where clause for a particular category """

    category = str(category)
    if category and recurse:
        # We're recursing and aren't in /, so add the prefix clause
        return orm.select(
            e for e in query
            if e.category == category or e.category.startswith(category + '/')
        )

    if not recurse:
        # We're not recursing, so we need an exact match on a possibly-empty
        # category
        return orm.select(e for e in query if e.category == category)

    # We're recursing and have no category, which means we're doing nothing
    return query


def where_before_entry(query, ref):
    """ Generate a where clause for prior entries

    ref -- The entry of reference
    """
    return orm.select(
        e for e in query
        if e.local_date < ref.local_date or
        (e.local_date == ref.local_date and e.id < ref.id)
    )


def where_after_entry(query, ref):
    """ Generate a where clause for later entries

    ref -- the entry of reference
    """
    return orm.select(
        e for e in query
        if e.local_date > ref.local_date or
        (e.local_date == ref.local_date and
         e.id > ref.id
         )
    )


def where_entry_last(query, ref):
    """ Generate a where clause where this is the last entry

    ref -- the entry of reference
    """
    return orm.select(
        e for e in query
        if e.local_date < ref.local_date or
        (e.local_date == ref.local_date and
         e.id <= ref.id
         )
    )


def where_entry_first(query, ref):
    """ Generate a where clause where this is the first entry

    ref -- the entry of reference
    """
    return orm.select(
        e for e in query
        if e.local_date > ref.local_date or
        (e.local_date == ref.local_date and
         e.id >= ref.id
         )
    )


def where_entry_type(query, entry_type):
    """ Generate a where clause for entries of certain types

    entry_type -- one or more entries to check against
    """
    if isinstance(entry_type, (list, set, tuple)):
        return orm.select(e for e in query if e.entry_type in entry_type)
    return orm.select(e for e in query if e.entry_type == entry_type)


def where_entry_type_not(query, entry_type):
    """ Generate a where clause for entries that aren't of certain types

    entry_type -- one or more entries to check against
    """
    if isinstance(entry_type, (list, set, tuple)):
        return orm.select(e for e in query if e.entry_type not in entry_type)
    return orm.select(e for e in query if e.entry_type != entry_type)


def where_entry_tag(query, tag):
    """ Generate a where clause for entries with the given tag """
    if isinstance(tag, (list, set, tuple)):
        tags = [t.lower() for t in tag]
        return orm.select(e for e in query for t in e.tags if t.key in tags)
    return orm.select(e for e in query for t in e.tags if t.key == tag.lower())


def where_entry_date(query, datespec):
    """ Where clause for entries which match a textual date spec

    datespec -- The date spec to check for, in YYYY[[-]MM[[-]DD]] format
    """
    date, interval, _ = utils.parse_date(datespec)
    start_date, end_date = date.span(interval)

    return orm.select(
        e for e in query if
        e.local_date >= start_date.naive and
        e.local_date <= end_date.naive
    )


def get_entry(entry):
    """ Helper function to get an entry by ID or by object """

    if hasattr(entry, 'id'):
        return entry

    if isinstance(entry, (int, str)):
        return model.Entry.get(id=int(entry))
    raise ValueError("entry is of unknown type {}".format(type(entry)))


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

    query = model.Entry.select()

    # primarily restrict by publication status
    if spec.get('_deleted', False):
        query = where_entry_deleted(query)
    elif spec.get('future', False):
        query = where_entry_visible_future(query)
    else:
        query = where_entry_visible(query)

    # restrict by category
    if spec.get('category') is not None:
        path = str(spec.get('category', ''))
        recurse = spec.get('recurse', False)
        query = where_entry_category(query, path, recurse)

    if spec.get('entry_type') is not None:
        query = where_entry_type(query, spec['entry_type'])

    if spec.get('entry_type_not') is not None:
        query = where_entry_type_not(query, spec['entry_type_not'])

    if spec.get('tag') is not None:
        query = where_entry_tag(query, spec['tag'])

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

    return query.distinct()
