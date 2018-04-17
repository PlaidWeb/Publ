# queries.py
# Collection of commonly-used queries

from . import model, utils
import arrow
import re


def where_entry_visible():
    # Generate a where clause for currently-visible entries
    return (model.Entry.status == model.PublishStatus.PUBLISHED) |
        (
            (model.Entry.status == model.PublishStatus.SCHEDULED) &
            (model.Entry.entry_date <= arrow.utcnow().datetime)
        )


def where_entry_visible_future():
    # Generate a where clause for entries that are visible now or in the future
    return (
        (model.Entry.status == model.PublishStatus.PUBLISHED) |
        (model.Entry.status == model.PublishStatus.SCHEDULED)
    )


def where_entry_category(category, recurse=False):
    # Generate a where clause for a particular category
    if category or not recurse:
        cat_where = (model.Entry.category == category)

        if recurse:
            # We're recursing and aren't in /, so add the prefix clause
            cat_where = cat_where | (
                model.Entry.category.startswith(category + '/'))
    else:
        cat_where = True

    return cat_where


def where_before_entry(entry):
    # Generate a where clause for prior entries
    return (model.Entry.entry_date < entry.entry_date) | (
        (model.Entry.entry_date == entry.entry_date) &
        (model.Entry.id < entry.id)
    )


def where_after_entry(entry):
    # Generate a where clause for later entries
    return (model.Entry.entry_date > entry.entry_date) | (
        (model.Entry.entry_date == entry.entry_date) &
        (model.Entry.id > entry.id)
    )


def where_entry_last(entry):
    # Generate a where clause where this is the last entry
    return (model.Entry.entry_date < entry.entry_date) | (
        (model.Entry.entry_date == entry.entry_date) &
        (model.Entry.id <= entry.id)
    )


def where_entry_first(entry):
    # Generate a where clause where this is the first entry
    return (model.Entry.entry_date > entry.entry_date) | (
        (model.Entry.entry_date == entry.entry_date) &
        (model.Entry.id >= entry.id)
    )


def where_entry_type(entry_type):
    # Generate a where clause for entries of certain types
    if isinstance(entry_type, list):
        return (model.Entry.entry_type << entry_type)
    else:
        return (model.Entry.entry_type == entry_type)


def where_entry_type_not(entry_type):
    # Generate a where clause for entries that aren't of certain types
    if isinstance(entry_type, list):
        return (model.Entry.entry_type.not_in(entry_type))
    else:
        return (model.Entry.entry_type != entry_type)


def where_entry_date(datespec):
    # Where clause for entries which match a textual date spec
    date, interval, _ = utils.parse_date(datespec)
    start_date, end_date = date.span(interval)

    return ((model.Entry.entry_date >= start_date.datetime) &
            (model.Entry.entry_date <= end_date.datetime))


def get_entry(entry):
    # Get an entry by ID or by object
    from .entry import Entry
    if isinstance(entry, (Entry, model.Entry, utils.CallableProxy)):
        return entry
    if isinstance(entry, (int, str)):
        return model.Entry.get(model.Entry.id == int(entry))
    raise ValueError("entry is of unknown type {}".format(type(entry)))


def build_query(spec):
    # build the where clause based on a view specification

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
        where = where & where_entry_before(get_entry(spec['before']))

    if 'after' in spec:
        where = where & where_query_after(get_entry(spec['after']))

    return where
