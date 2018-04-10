# queries.py
# Collection of commonly-used queries

from . import model, utils
import arrow
import re

''' Where clause for currently-visible entries '''
where_entry_visible = (
    (model.Entry.status == model.PublishStatus.PUBLISHED) |
    (
        (model.Entry.status == model.PublishStatus.SCHEDULED) &
        (model.Entry.entry_date < arrow.now().datetime)
    )
)

''' Where clause for entries visible in the future '''
where_entry_visible_future = (
    (model.Entry.status == model.PublishStatus.PUBLISHED) |
    (model.Entry.status == model.PublishStatus.SCHEDULED)
)

''' Where clause for entries in a category '''
def where_entry_category(category, recurse=False):
    if category or not recurse:
        cat_where = (model.Entry.category == category)

        if recurse:
            # We're recursing and aren't in /, so add the prefix clause
            cat_where = cat_where | (model.Entry.category.startswith(category + '/'))
    else:
        cat_where = True

    return cat_where

''' Where clauses for preceding entries '''
def where_before_entry(entry):
    return (model.Entry.entry_date < entry.entry_date) | (
        (model.Entry.entry_date == entry.entry_date) &
        (model.Entry.id < entry.id)
    )

''' Where clause for succeeding entries '''
def where_after_entry(entry):
    return (model.Entry.entry_date > entry.entry_date) | (
        (model.Entry.entry_date == entry.entry_date) &
        (model.Entry.id > entry.id)
    )

''' Where clauses for entries where this is the last one '''
def where_entry_last(entry):
    return (model.Entry.entry_date < entry.entry_date) | (
        (model.Entry.entry_date == entry.entry_date) &
        (model.Entry.id <= entry.id)
    )

''' Where clause for entries where this is the first one '''
def where_entry_first(entry):
    return (model.Entry.entry_date > entry.entry_date) | (
        (model.Entry.entry_date == entry.entry_date) &
        (model.Entry.id >= entry.id)
    )

''' Where clauses for entry type inclusion '''
def where_entry_type(entry_type):
    if type(entry_type) == str:
        return (model.Entry.entry_type == entry_type)
    else:
        return (model.Entry.entry_type << entry_type)

''' Where clauses for entry type exclusion '''
def where_entry_type_not(entry_type):
    if type(entry_type) == str:
        return (model.Entry.entry_type != entry_type)
    else:
        return (model.Entry.entry_type.not_in(entry_type))

''' Where clauses for a date range '''
def where_entry_date(datespec):
    date, interval, _ = utils.parse_date(datespec)
    start_date, end_date = date.span(interval)

    print('date', date, interval)
    print('range', start_date, end_date)

    return ((model.Entry.entry_date >= start_date.datetime) &
        (model.Entry.entry_date <= end_date.datetime))

''' Get an entry by ID or by object '''
def get_entry(entry):
    if type(entry) == int or type(entry) == str:
        return model.Entry.get(model.Entry.id == int(entry))
    return entry

''' Generate a full where clause based on a restriction specification '''
def build_query(spec):
    # primarily restrict by publication status
    if spec.get('future', False):
        where = where_entry_visible_future
    else:
        where = where_entry_visible

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
