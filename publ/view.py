# view.py
""" A view of entries """

from __future__ import absolute_import, with_statement

import arrow
import flask

from . import model, utils, queries
from .entry import Entry

# Prioritization list for page/offset/whatever
OFFSET_PRIORITY = ['date', 'last', 'first', 'before', 'after']

# Prioritization list for pagination type
#
# NOTE: date appears in here too so that if it appears as an offset it
# overrides the count
PAGINATION_PRIORITY = ['date', 'count']


#: Ordering queries for different sort orders
ORDER_BY = {
    'newest': [-model.Entry.entry_date, -model.Entry.id],
    'oldest': [model.Entry.entry_date, model.Entry.id],
    'title': [model.Entry.title, model.Entry.id]
}

REVERSE_ORDER_BY = {
    'newest': [model.Entry.entry_date, model.Entry.id],
    'oldest': [-model.Entry.entry_date, -model.Entry.id],
    'title': [-model.Entry.title, -model.Entry.id]
}


class View:
    # pylint: disable=too-many-instance-attributes,too-few-public-methods
    """ A view of entries """

    def __init__(self, input_spec=None):
        """ Generate a view.

        input_spec -- the parameters to the view. In addition to the values provided
        to queries.build_query, this also takes the following keys:
            count -- How many entries to include in a page
            order -- How to order the entries ('newest' or 'oldest')
        """

        # filter out any priority override things
        spec = {
            k: v for k, v in input_spec.items()
            if k not in [*OFFSET_PRIORITY, *PAGINATION_PRIORITY]
        }

        # pull in the first offset type that appears
        for offset in OFFSET_PRIORITY:
            if offset in input_spec:
                spec[offset] = input_spec[offset]
                break

        # pull in the first page type that appears
        for pagination in PAGINATION_PRIORITY:
            if pagination in input_spec:
                spec[pagination] = input_spec[pagination]
                break

        self.spec = spec
        self._where = queries.build_query(spec)
        self._query = model.Entry.select().where(self._where)

        if 'count' in spec:
            self._query = self._query.limit(spec['count'])

        self._order_by = spec.get('order', 'newest')
        self._entries = self._query.order_by(*ORDER_BY[self._order_by])

        self.link = utils.CallableProxy(self._link)

        if 'date' in self.spec:
            _, self.type, _ = utils.parse_date(self.spec['date'])
        elif 'count' in self.spec:
            self.type = 'count'
        else:
            self.type = None

    def _spec_filtered(self):
        # Return a version of our spec where all pagination stuff has been
        # removed
        return {k: v for k, v in self.spec.items()
                if k not in [*OFFSET_PRIORITY, *PAGINATION_PRIORITY]}

    def __str__(self):
        return str(self._link())

    def _link(self, template='', absolute=False):
        args = {}
        for k, val in self.spec.items():
            if k in ['date', 'last', 'first', 'before', 'after']:
                if isinstance(val, (str, int)):
                    args[k] = val
                elif hasattr(val, 'id'):
                    # the item was an object, so we want the object's id
                    args[k] = val.id
                else:
                    raise ValueError(
                        "key {} is of type {}".format(k, type(val)))

        return flask.url_for('category',
                             **args,
                             template=template,
                             category=self.spec.get('category'),
                             _external=absolute)

    @property
    def first(self):
        """ Gets the first entry in the view """
        return self.entries[0] if self.entries else None

    @property
    def last(self):
        """ Gets the last entry in the view """
        return self.entries[-1] if self.entries else None

    def __getattr__(self, name):
        """ Lazy evaluation of properties """
        # pylint: disable=attribute-defined-outside-init

        if name == 'entries':
            self.entries = [Entry(e) for e in self._entries]
            return self.entries

        if name == 'last_modified':
            # Get the most recent entry in the view
            try:
                latest = self._query.order_by(-model.Entry.entry_date)[0]
                self.last_modified = arrow.get(Entry(latest).last_modified)
            except IndexError:
                self.last_modified = arrow.get()
            return self.last_modified

        if name == 'previous' or name == 'next':
            self.previous, self.next = self._get_pagination()
            return getattr(self, name)

        if name == 'newest' or name == 'oldest':
            if self._order_by == 'newest':
                self.newest, self.oldest = self.first, self.last
            elif self._order_by == 'oldest':
                self.newest, self.oldest = self.last, self.first
            else:
                raise ValueError(
                    'newest/oldest not supported on sort type {}'.format(self._order_by))
            return getattr(self, name)

        raise AttributeError("Unknown view attribute {}".format(name))

    def _get_pagination(self):
        """ Compute the next/previous pages from this view.

        Returns a tuple of previous page, next page.
        """

        # https://github.com/fluffy-critter/Publ/issues/35
        oldest = self.oldest
        newest = self.newest
        oldest_neighbor = self.oldest.previous if oldest else None
        newest_neighbor = self.newest.next if newest else None

        base = self._spec_filtered()

        if 'count' in self.spec:
            return self._get_count_pagination(base, oldest_neighbor, newest_neighbor)

        if 'date' in self.spec:
            return self._get_date_pagination(base, oldest_neighbor, newest_neighbor)

        # we're not paginating?
        return None, None

    def _get_count_pagination(self, base, oldest_neighbor, newest_neighbor):
        """ Compute the pagination for count paginations """
        count = int(self.spec['count'])

        if self._order_by == 'newest':
                # Newest first; next page ends at the one prior to our oldest
            if oldest_neighbor:
                next_view = View({**base, 'last': oldest_neighbor})
            else:
                next_view = None

            # Previous page ends at [count] after our newest
            if newest_neighbor:
                # Ask for the next chunk of items in ascending order
                scan_view = View({**base,
                                  'first': newest_neighbor,
                                  'count': count,
                                  'order': 'oldest'})
                # our previous page starts at the last entry (ascending)
                previous_view = (View({**base, 'last': scan_view.entries[-1]})
                                 if scan_view.entries else None)
            else:
                previous_view = None

            return previous_view, next_view

        if self._order_by == 'oldest':
            # Oldest first; next page begins with our newest entry
            if newest_neighbor:
                next_view = View({**base, 'first': newest_neighbor})
            else:
                next_view = None

            # Previous page starts at [count] before our newest
            if oldest_neighbor:
                # Ask for the previous chunk of items in descending order
                scan_view = View({**base,
                                  'last': oldest_neighbor,
                                  'count': count,
                                  'order': 'newest'})
                # our previous page starts at the last entry (descending)
                previous_view = (View({**base, 'first': scan_view.entries[-1]})
                                 if scan_view.entries else None)
            else:
                previous_view = None

            return previous_view, next_view

        return None, None

    def _get_date_pagination(self, base, oldest_neighbor, newest_neighbor):
        """ Compute the pagination for date-based views """
        _, _, date_format = utils.parse_date(self.spec['date'])

        if self._order_by == 'newest':
                # newest first; next page contains the oldest neighbor
            next_date = oldest_neighbor.date.format(
                date_format) if oldest_neighbor else None
            previous_date = newest_neighbor.date.format(
                date_format) if newest_neighbor else None
        elif self._order_by == 'oldest':
            # oldest first; next page contains the newest neighbor
            next_date = newest_neighbor.date.format(
                date_format) if newest_neighbor else None
            previous_date = oldest_neighbor.date.format(
                date_format) if oldest_neighbor else None
        else:
            raise ValueError(
                "Unsupported sort {} for date pagination".format(self._order_by))

        previous_view = View({**base, 'date': previous_date}) if previous_date else None
        next_view = View({**base, 'date': next_date}) if next_date else None

        return previous_view, next_view

    def __call__(self, **restrict):
        return View({**self.spec, **restrict})


def get_view(**kwargs):
    """ Wrapper function for constructing a view from scratch """
    return View(input_spec=kwargs)
