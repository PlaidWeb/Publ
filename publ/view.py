# view.py
# A view of entries

from . import model, utils, queries
from .entry import Entry
import arrow
import flask

''' Prioritization list for page/offset/whatever '''
offset_priority = ['date', 'last', 'first', 'before', 'after']

''' Prioritization list for pagination type

NOTE: date appears in here too so that if it appears as an offset it overrides the limit

'''
pagination_priority = ['date', 'limit']

class View:
    def __init__(self, input_spec=None):
        # filter out any priority override things
        spec = {k:v for k,v in input_spec.items() if k not in offset_priority and k not in pagination_priority}

        # pull in the first offset type that appears
        for offset in offset_priority:
            if offset in input_spec:
                spec[offset] = input_spec[offset]
                break

        # pull in the first page type that appears
        for pagination in pagination_priority:
            if pagination in input_spec:
                spec[pagination] = input_spec[pagination]
                break

        self.spec = spec

        self._where = queries.build_query(spec)

        self._query = model.Entry.select().where(self._where)

        if 'limit' in spec:
            self._query = self._query.limit(spec['limit'])

        self._order_by = spec.get('order', 'newest')
        if self._order_by == 'newest':
            self._order = -model.Entry.entry_date
            self._reverse = model.Entry.entry_date
        elif self._order_by == 'oldest':
            self._order = model.Entry.entry_date
            self._reverse = -model.Entry.entry_date
        else:
            raise ValueError("Unknown sort order '{}'".format(sort_order))

        self.link = utils.CallableProxy(self._link)

    ''' Return a spec where all pagination stuff has been removed '''
    def _spec_filtered(self):
        return {k:v for k,v in self.spec.items()
            if k not in offset_priority
            and k not in pagination_priority}

    def __str__(self):
        return str(self._link())

    def _link(self, template='', absolute=False):
        args = {}
        for k,v in self.spec.items():
            if k in ['date','last','first','before','after']:
                if type(v) == str or type(v) == int:
                    args[k] = v
                else:
                    # the item was an object, so we actually want the object's id
                    args[k] = v.id

        return flask.url_for('category',
            **args,
            template=template,
            category=self.spec.get('category'),
            _external=absolute)

    def __getattr__(self, name):
        if name == 'entries':
            self.entries = [Entry(e) for e in self._query.order_by(self._order)]
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
            entries = self.entries
            first = entries[0]
            last = entries[-1]
            if self._order_by == 'newest':
                self.newest, self.oldest = first, last
            elif self._order_by == 'oldest':
                self.newest, self.oldest = last, first
            else:
                raise ValueError('newest/oldest not supported on sort type {}'.format(self._order_by))
            return getattr(self, name)

    ''' Returns the views (if any) for the previous or next page, in that order

    Note: "next page" is in terms of display order; newest first means next = older
    '''
    def _get_pagination(self):
        # TODO https://github.com/fluffy-critter/Publ/issues/35
        oldest = self.oldest
        newest = self.newest
        oldest_neighbor = self.oldest.previous if oldest else None
        newest_neighbor = self.newest.next if newest else None

        base = self._spec_filtered()

        if 'limit' in self.spec:
            # limiting by count
            count = int(self.spec['limit'])

            if self._order_by == 'newest':
                # Newest first; next page ends at the one prior to our oldest
                if oldest_neighbor:
                    next_view = View({**base, 'last': oldest_neighbor})
                else:
                    next_view = None

                # Previous page ends at [limit] after our newest
                if newest_neighbor:
                    # Ask for the next chunk of items in ascending order
                    scan_view = View({**base,
                        'first': newest_neighbor,
                        'limit': count,
                        'order': 'oldest'})
                    # our previous page starts at the last entry (ascending)
                    previous_view = View({**base, 'last': scan_view.entries[-1]})
                else:
                    previous_view = None

                return previous_view, next_view

            if self._order_by == 'oldest':
                # Oldest first; next page begins with our newest entry
                if newest_neighbor:
                    next_view = View({**base, 'first': newest_neighbor})
                else:
                    next_view = None

                # Previous page starts at [limit] before our newest
                if oldest_neighbor:
                    # Ask for the previous chunk of items in descending order
                    scan_view = View({**base,
                        'last': oldest_neighbor,
                        'limit': count,
                        'order': 'newest'})
                    scan_entries = scan_view.entries
                    # our previous page starts at the last entry (descending)
                    previous_view = View({**base, 'first': scan_view.entries[-1]})
                else:
                    previous_view = None

                return previous_view, next_view

        if 'date' in self.spec:
            # we're limiting by date
            _, _, format = utils.parse_date(self.spec['date'])

            if self._order_by == 'newest':
                # newest first; next page contains the oldest neighbor
                next_date = oldest_neighbor.date.format(format) if oldest_neighbor else None
                previous_date = newest_neighbor.date.format(format) if newest_neighbor else None
            elif self._order_by == 'oldest':
                # oldest first; next page contains the newest neighbor
                next_date = newest_neighbor.date.format(format) if newest_neighbor else None
                previous_date = oldest_neighbor.date.format(format) if oldest_neighbor else None
            else:
                raise ValueError("Unsupported sort {} for date pagination".format(self._order_by))

            previous_view = View({**base, 'date': previous_date}) if previous_date else None
            next_view = View({**base, 'date': next_date}) if next_date else None

            return previous_view, next_view

        # we're not paginating?
        return None, None

    def __call__(self, **restrict):
        return View({**self.spec, **restrict})

def get_view(**kwargs):
    return View(spec=kwargs)
