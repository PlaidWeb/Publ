# queries.py
# Collection of commonly-used queries

from . import model
import arrow

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
