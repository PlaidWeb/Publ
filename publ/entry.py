# item.py
# Functions for handling content items

import markdown
import os
import shutil
import re
import arrow
import email
import uuid
import tempfile
import flask
import logging
import random

import config

from . import model, queries
from . import path_alias
from . import markdown
from .utils import CallableProxy

logger = logging.getLogger(__name__)

class Entry:
    def __init__(self, record):
        self._record = record   # index record
        self._message = None    # actual message payload, lazy-loaded

        self.date = arrow.get(record.entry_date)

        self.link = CallableProxy(self._link)
        self.permalink = CallableProxy(self._permalink)

        self.next = CallableProxy(self._next)
        self.previous = CallableProxy(self._previous)

    ''' get a link to the entry, potentially pre-redirected '''
    def _link(self, **kwargs):
        if self._record.redirect_url:
            return self._record.redirect_url

        return self._permalink(**kwargs)

    def _permalink(self, absolute=False, expand=True):
        return flask.url_for('entry',
            entry_id=self._record.id,
            category=self._record.category if expand else None,
            slug_text=self._record.slug_text if expand else None,
            _external=absolute)

    ''' Ensure the message payload is loaded '''
    def _load(self):
        if not self._message:
            filepath = self._record.file_path
            try:
                with open(filepath, 'r') as file:
                    self._message = email.message_from_file(file)
            except FileNotFoundError:
                expire_record(self._record)

            body, _, more = self._message.get_payload().partition('\n.....\n')
            if not more and body.startswith('.....\n'):
                # The entry began with a cut, which failed to parse.
                # This rule is easier/faster than dealing with a regex from hell.
                more = body[6:]
                body = ''

            # TODO https://github.com/fluffy-critter/Publ/issues/9
            # Not only will we want to accept args on the markdown path but
            # we'll want to ignore them on the HTML path (or maybe implement
            # a VERY basic template processor even for HTML)
            _,ext = os.path.splitext(filepath)
            is_markdown = ext == '.md'
            self.body = CallableProxy(self._get_markup, body or '', is_markdown)
            self.more = CallableProxy(self._get_markup, more or '', is_markdown)

            self.last_modified = arrow.get(os.stat(self._record.file_path).st_mtime).to(config.timezone)

            return True
        return False

    @staticmethod
    def _get_markup(text, is_markdown, **kwargs):
        if is_markdown:
            return flask.Markup(markdown.format(text), **kwargs)
        return flask.Markup(text)

    ''' attribute getter, to convert attributes to index and payload lookups '''
    def __getattr__(self, name):
        if name == 'previous':
            # Get the previous entry in the same category (by date)
            self.previous = self.previous_in(self._record.category,False)
            return self.previous

        if name == 'next':
            # Get the next entry in the same category (by date)
            self.next = self.next_in(self._record.category,False)
            return self.next

        if hasattr(self._record, name):
            return getattr(self._record, name)

        if self._load():
            # We just loaded which modifies our own attrs, so rerun the default logic
            return getattr(self, name)

        return self._message.get(name)

    def _get_sibling(self,query):
        query = query.limit(1)
        return Entry(query[0]) if query.count() else None

    ''' Get the previous item in any particular category '''
    def _previous(self,**kwargs):
        spec = {
            'category': self._record.category,
            'recurse': 'category' in kwargs
        }
        spec.update(kwargs)

        return self._get_sibling(model.Entry.select().where(
            queries.build_query(spec) &
            queries.where_before_entry(self._record)
            ).order_by(-model.Entry.entry_date, -model.Entry.id))

    ''' Get the next item in any particular category '''
    def _next(self,**kwargs):
        spec = {
            'category': self._record.category,
            'recurse': 'category' in kwargs
        }
        spec.update(kwargs)

        return self._get_sibling(
            model.Entry.select().where(
                queries.build_query(spec) &
                queries.where_after_entry(self._record)
            ).order_by(model.Entry.entry_date, model.Entry.id))

    ''' Get a single header on an entry '''
    def get(self, name):
        self._load()
        return self._message.get(name)

    ''' Get all related headers on an entry, as an iterable list '''
    def get_all(self, name):
        self._load()
        return self._message.get_all(name) or []

''' convert a title into a URL-friendly slug '''
def make_slug(title):
    # TODO https://github.com/fluffy-critter/Publ/issues/16
    # this should probably handle things other than English ASCII, and also
    # some punctuation should just be outright removed (quotes/apostrophes/etc)
    return re.sub(r"[^a-zA-Z0-9.]+", r" ", title).strip().replace(' ','-')

''' Attempt to guess the title from the filename '''
def guess_title(basename):
    base,_ = os.path.splitext(basename)
    return re.sub(r'[ _-]+', r' ', base).title()

''' scan a file and put it into the index '''
def scan_file(fullpath, relpath, assign_id):
    try:
        with open(fullpath, 'r') as file:
            entry = email.message_from_file(file)
    except FileNotFoundError:
        # The file doesn't exist, so remove it from the index
        record = model.Entry.get_or_none(file_path=fullpath)
        if record:
            expire_record(record)
        return

    with model.lock:
        warn_duplicate = False

        if 'Entry-ID' in entry:
            entry_id = int(entry['Entry-ID'])
        else:
            entry_id = None

        # See if we-ve inadvertently duplicated an entry ID
        if entry_id:
            other_entry = model.Entry.get_or_none(model.Entry.id == entry_id)
            if (other_entry
                and other_entry.file_path != fullpath
                and os.path.isfile(other_entry.file_path)):
                warn_duplicate = entry_id
                entry_id = None

        fixup_needed = entry_id == None or not 'Date' in entry or not 'UUID' in entry

        # Do we need to assign a new ID?
        if not entry_id:
            if not assign_id:
                # We're not assigning IDs yet
                return False

            # Generate an ID randomly. Experiments find that this approach
            # averages around 0.25 collisions per ID generated while keeping the
            # entry ID reasonably short. count*N+C averages 1/(N-1) collisions
            # per ID.
            limit = model.Entry.select().count()*5 + 10
            entry_id = random.randint(1, limit)
            while model.Entry.get_or_none(model.Entry.id == entry_id):
                entry_id = random.randint(1, limit)

            if warn_duplicate is not False:
                logger.warning("Entry '%s' had ID %d, already assigned to '%s'. Reassigned to %d",
                    fullpath, warn_duplicate, other_entry.file_path, entry_id)

        basename = os.path.basename(relpath)
        title = entry['title'] or guess_title(basename)

        values = {
            'file_path': fullpath,
            'category': entry.get('Category', os.path.dirname(relpath)),
            'status': model.PublishStatus[entry.get('Status', 'SCHEDULED').upper()],
            'entry_type': entry.get('Entry-Type', ''),
            'slug_text': make_slug(entry['Slug-Text'] or title),
            'redirect_url': entry['Redirect-To'],
            'title': title,
        }

        if 'Date' in entry:
            entry_date = arrow.get(entry['Date'], tzinfo=config.timezone)
            del entry['Date']
            entry['Date'] = entry_date.format()
        else:
            entry_date = arrow.get(os.stat(fullpath).st_ctime).to(config.timezone)
            entry['Date'] = entry_date.format()
        values['entry_date'] = entry_date.datetime

        if entry_id != None:
            logger.debug("creating %s with id %d", fullpath, entry_id)
            record, created = model.Entry.get_or_create(id=entry_id, defaults=values)
        else:
            logger.debug("creating %s with new id", fullpath)
            record, created = model.Entry.get_or_create(file_path=fullpath, defaults=values)

        if not created:
            logger.debug("Reusing existing entry %d", record.id)
            record.update(**values).where(model.Entry.id == record.id).execute()

        # Update the entry ID
        del entry['Entry-ID']
        entry['Entry-ID'] = str(record.id)

        if not 'UUID' in entry:
            entry['UUID'] = str(uuid.uuid4())

        # add other relationships to the index
        for alias in entry.get_all('Path-Alias', []):
            path_alias.set_alias(alias, entry=record)
        for alias in entry.get_all('Path-Unalias', []):
            path_alias.remove_alias(alias)

        if fixup_needed:
            with tempfile.NamedTemporaryFile('w', delete=False) as file:
                tmpfile = file.name
                file.write(str(entry))
            shutil.move(tmpfile, fullpath)

        return record

def expire_record(record):
    with model.lock:
        # This entry no longer exists so delete it, and anything that references it
        # SQLite doesn't support cascading deletes so let's just clean up manually
        model.PathAlias.delete().where(model.PathAlias.redirect_entry == record).execute()
        record.delete_instance(recursive=True)


