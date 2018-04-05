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

import config

from . import model
from . import path_alias
from .markdown import MarkdownText
from .utils import SelfStrCall

logger = logging.getLogger(__name__)

''' Link for an entry; defaults to an individual page '''
class EntryLink(SelfStrCall):
    def __init__(self, record):
        self._record = record

    def __call__(self, absolute=False, expand=True):
        # TODO https://github.com/fluffy-critter/Publ/issues/15
        # add arguments for category/view, shortlink, etc.
        if self._record.redirect_url:
            return self._record.redirect_url

        return flask.url_for('entry',
            entry_id=self._record.id,
            category=expand and self._record.category or None,
            slug_text=expand and self._record.slug_text or None,
            _external=absolute)

''' Permalink for an entry '''
class EntryPermalink(SelfStrCall):
    def __init__(self, record):
        self._record = record

    def __call__(self, absolute=False, expand=True):
        return flask.url_for('entry',
            entry_id=self._record.id,
            category=expand and self._record.category or None,
            slug_text=expand and self._record.slug_text or None,
            _external=absolute)

class Entry:
    def __init__(self, record):
        self._record = record   # index record
        self._message = None    # actual message payload, lazy-loaded

        self.date = arrow.get(record.entry_date)

        self.link = EntryLink(self._record)
        self.permalink = EntryPermalink(self._record)

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
            if ext == '.md':
                self.body = body and MarkdownText(body) or None
                self.more = more and MarkdownText(more) or None
            else:
                self.body = body and body or None
                self.more = more and more or None


            self.last_modified = arrow.get(os.stat(self._record.file_path).st_mtime).to(config.timezone)

            return True
        return False

    ''' attribute getter, to convert attributes to index and payload lookups '''
    def __getattr__(self, name):
        if name == 'previous':
            # Get the previous entry in the same category (by date)
            sibling = model.Entry.select().where(
                (model.Entry.category == self._record.category) & (
                    (model.Entry.entry_date < self._record.entry_date) | (
                        (model.Entry.entry_date == self._record.entry_date) & (model.Entry.id < self._record.id)
                    )
                )).order_by(-model.Entry.entry_date).limit(1)
            self.previous = sibling.count() and Entry(sibling[0]) or None
            return self.previous

        if name == 'next':
            # Get the next entry in the same category (by date)
            sibling = model.Entry.select().where(
                (model.Entry.category == self._record.category) & (
                    (model.Entry.entry_date > self._record.entry_date) | (
                        (model.Entry.entry_date == self._record.entry_date) & (model.Entry.id > self._record.id)
                    )
                )).order_by(model.Entry.entry_date).limit(1)
            self.previous = sibling.count() and Entry(sibling[0]) or None
            return self.previous

        if hasattr(self._record, name):
            return getattr(self._record, name)

        if self._load():
            # We just loaded which modifies our own attrs, so rerun the default logic
            return getattr(self, name)

        return self._message.get(name)

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
    # this should probably handle things other than English ASCII...
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
        if 'Entry-ID' in entry:
            entry_id = int(entry['Entry-ID'])
        elif not assign_id:
            return False
        else:
            entry_id = None

        fixup_needed = entry_id == None or not 'Date' in entry or not 'UUID' in entry

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
            entry_date = arrow.get(entry['Date'])
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


