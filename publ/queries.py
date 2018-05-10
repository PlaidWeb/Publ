# queries.py
""" Collection of commonly-used queries """

from __future__ import absolute_import, with_statement

import arrow

from . import model, utils


def where_entry_visible(date=None):
    """ Generate a where clause for currently-visible entries

    Arguments:

    date -- The date to generate it relative to (defaults to right now)
    """

    return (
        (model.Entry.status == model.PublishStatus.PUBLISHED) |
        (
            (model.Entry.status == model.PublishStatus.SCHEDULED) &
            (model.Entry.entry_date <= (date or arrow.utcnow().datetime))
        )
    )


def where_entry_visible_future():
    """ Generate a where clause for entries that are visible now or in the future """
    return (
        (model.Entry.status == model.PublishStatus.PUBLISHED) |
        (model.Entry.status == model.PublishStatus.SCHEDULED)
    )


def where_entry_category(category, recurse=False):
    """ Generate a where clause for a particular category """

    if category or not recurse:
        cat_where = (model.Entry.category == str(category))

        if recurse:
            # We're recursing and aren't in /, so add the prefix clause
            cat_where = cat_where | (
                model.Entry.category.startswith(str(category) + '/'))
    else:
        cat_where = True

    return cat_where


def where_before_entry(entry):
    """ Generate a where clause for prior entries

    entry -- The entry of reference
    """
    return (model.Entry.entry_date < entry.entry_date) | (
        (model.Entry.entry_date == entry.entry_date) &
        (model.Entry.id < entry.id)
    )


def where_after_entry(entry):
    """ Generate a where clause for later entries

    entry -- the entry of reference
    """
    return (model.Entry.entry_date > entry.entry_date) | (
        (model.Entry.entry_date == entry.entry_date) &
        (model.Entry.id > entry.id)
    )


def where_entry_last(entry):
    """ Generate a where clause where this is the last entry

    entry -- the entry of reference
    """
    return (model.Entry.entry_date < entry.entry_date) | (
        (model.Entry.entry_date == entry.entry_date) &
        (model.Entry.id <= entry.id)
    )


def where_entry_first(entry):
    """ Generate a where clause where this is the first entry

    entry -- the entry of reference
    """
    return (model.Entry.entry_date > entry.entry_date) | (
        (model.Entry.entry_date == entry.entry_date) &
        (model.Entry.id >= entry.id)
    )


def where_entry_type(entry_type):
    """ Generate a where clause for entries of certain types

    entry_type -- one or more entries to check against
    """
    if isinstance(entry_type, list):
        return model.Entry.entry_type << entry_type
    return model.Entry.entry_type == entry_type


def where_entry_type_not(entry_type):
    """ Generate a where clause for entries that aren't of certain types

    entry_type -- one or more entries to check against
    """
    if isinstance(entry_type, list):
        return model.Entry.entry_type.not_in(entry_type)
    return model.Entry.entry_type != entry_type


def where_entry_date(datespec):
    """ Where clause for entries which match a textual date spec

    datespec -- The date spec to check for, in YYYY[[-]MM[[-]DD]] format
    """
    date, interval, _ = utils.parse_date(datespec)
    start_date, end_date = date.span(interval)

    print('where_entry_date', start_date, end_date)

    return ((model.Entry.entry_date >= start_date.to('utc').datetime) &
            (model.Entry.entry_date <= end_date.to('utc').datetime))


def get_entry(entry):
    """ Helper function to get an entry by ID or by object """

    if hasattr(entry, 'id'):
        return entry

    if isinstance(entry, (int, str)):
        return model.Entry.get(model.Entry.id == int(entry))
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

    # primarily restrict by publication status
    if spec.get('future', False):
        where = where_entry_visible_future()
    else:
        where = where_entry_visible()

    # restrict by category
    if 'category' in spec or 'recurse' in spec:
        path = str(spec.get('category', ''))
        recurse = spec.get('recurse', False)
        where = where & where_entry_category(path, recurse)

    if 'entry_type' in spec:
        where = where & where_entry_type(spec['entry_type'])

    if 'entry_type_not' in spec:
        where = where & where_entry_type_not(spec['entry_type_not'])

    if 'date' in spec:
        where = where & where_entry_date(spec['date'])

    if 'last' in spec:
        where = where & where_entry_last(get_entry(spec['last']))

    if 'first' in spec:
        where = where & where_entry_first(get_entry(spec['first']))

    if 'before' in spec:
        where = where & where_before_entry(get_entry(spec['before']))

    if 'after' in spec:
        where = where & where_after_entry(get_entry(spec['after']))

    return where
