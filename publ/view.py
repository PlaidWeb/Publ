# view.py
# A view of entries

from . import model, utils, queries
from .entry import Entry
import arrow
import flask

'''
TODO: figure out the actual API; https://github.com/fluffy-critter/Publ/issues/13

expected view specs:

limit - number of entries to limit to
category - top-level category to retrieve
recurse - whether to recurse into subcategories
date - date spec for the view, one of:
    YYYY - just the year
    YYYYMM - year and month
    YYYYMMDD - year/month/day
    YYYY_WW - year/week
start_entry - the first entry to show (in the sort order)
last_entry - the last entry to show (in the sort order)
prev_entry - show entries after this one (in the sort order)
next_entry - show entries prior to this one (in the sort order)
sort - sorting spec, at the very least:
    newest
    oldest
    title
future - whether to show entries from the future
'''

class View:
    def __init__(self, spec=None):
        self.spec = spec

        if 'date' in self.spec:
            # date overrides limit
            if 'limit' in self.spec: del self.spec['limit']

        self._where = queries.build_query(spec or {})

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

    def __str__(self):
        return str(self._link())

    def _link(self, template='', absolute=False):
        args = {k:v for k,v in self.spec.items() if k in ['date','last','first','before','after']}

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

    def _get_pagination(self):
        if not self.entries or not len(self.entries):
            return None, None

        if 'limit' in self.spec:
            # TODO
            raise ValueError('limit pagination not yet supported')

        if 'date' in self.spec:
            # we're limiting by date
            if self._order_by == 'newest':
                newest = self.entries[0]
                oldest = self.entries[-1]
            elif self._order_by == 'oldest':
                oldest = self.entries[0]
                newest = self.entries[-1]
            else:
                raise ValueError('attempted date-based limit on non-date-based sort {}'.format(self._order_by))

            previous_entry = oldest.previous
            next_entry = newest.next

            _, _, format = utils.parse_date(self.spec['date'])

            if previous_entry:
                previous_date = previous_entry.date.format(format)
                previous_view = View({**self.spec, 'date': previous_date})
            else:
                previous_view = None

            if next_entry:
                next_date = next_entry.date.format(format)
                next_view = View({**self.spec, 'date': next_date})
            else:
                next_view = None

            return previous_view, next_view

        # we're not paginating?
        return None, None

    def __call__(self, **restrict):
        return View({**self.spec, **restrict})

def get_view(**kwargs):
    return View(spec=kwargs)
