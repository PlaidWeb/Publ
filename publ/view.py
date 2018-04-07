# view.py
# A view of entries

from . import model, utils, queries
from .entry import Entry
import arrow

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
        self._where = queries.build_query(spec or {})

        # TODO https://github.com/fluffy-critter/Publ/issues/13 sorting
        self._query = model.Entry.select().where(self._where).order_by(-model.Entry.entry_date)

        if 'limit' in spec:
            self._query = self._query.limit(self.spec['limit'])

    def __getattr__(self, name):
        if name == 'entries':
            self.entries = [Entry(e) for e in self._query]
            return self.entries

        if name == 'last_modified':
            # Get the most recent entry in the view
            try:
                latest = self._query.order_by(-model.Entry.entry_date)[0]
                self.last_modified = arrow.get(Entry(latest).last_modified)
            except IndexError:
                self.last_modified = arrow.get()
            return self.last_modified

    def __call__(self, **restrict):
        return View({**self.spec, **restrict})

def get_view(**kwargs):
    return View(spec=kwargs)
