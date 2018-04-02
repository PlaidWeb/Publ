# item.py
# Functions for handling content items

import markdown
import os
import re
import arrow
import email
import uuid

import config

from . import model
from . import path_alias

class MarkdownText:
    def __init__(self, text):
        self._text = text

    def __str__(self):
        return self()

    def __call__(self, **kwargs):
        # TODO instance parser with image rendition support
        return markdown.markdown(self._text)

class Entry:
    def __init__(self, record):
        self._record = record   # index record
        self._message = None    # actual message payload, lazy-loaded

    ''' Ensure the message payload is loaded '''
    def _load(self):
        if not self._message:
            filepath = self._record.file_path
            with open(filepath, 'r') as file:
                self._message = email.message_from_file(file)

            body, _, more = self._message.get_payload().partition('\n~~~~~\n')

            _,ext = os.path.splitext(filepath)
            if ext == '.md':
                self.body = body and MarkdownText(body) or None
                self.more = more and MarkdownText(more) or None
            else:
                self.body = body and body or None
                self.more = more and more or None
            return True
        return False

    ''' attribute getter, to convert attributes to index and payload lookups '''
    def __getattr__(self, name):
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
    # TODO this should probably handle things other than English ASCII...
    return re.sub(r"[^a-zA-Z0-9]+", r"-", title.strip())

def scan_file(fullpath, relpath, assign_id):
    ''' scan a file and put it into the index '''
    with open(fullpath, 'r') as file:
        entry = email.message_from_file(file)

    entry_id = entry['Entry-ID']
    if entry_id == None and not assign_id:
        return False

    fixup_needed = entry_id == None or not 'Date' in entry or not 'UUID' in entry

    values = {
        'file_path': fullpath,
        'category': entry.get('Category', os.path.dirname(relpath)),
        'status': model.PublishStatus[entry.get('Status', 'PUBLISHED').upper()],
        'entry_type': model.EntryType[entry.get('Type', 'ENTRY').upper()],
        'slug_text': make_slug(entry['Slug-Text'] or entry['Title'] or os.path.basename(relpath)),
        'redirect_url': entry['Redirect-To'],
        'title': entry['Title'],
    }

    if 'Date' in entry:
        entry_date = arrow.get(entry['Date'])
    else:
        entry_date = arrow.get(os.stat(fullpath).st_ctime).to(config.timezone)
        entry['Date'] = entry_date.format()
    values['entry_date'] = entry_date.datetime

    if entry_id != None:
        record, created = model.Entry.get_or_create(id=entry_id, defaults=values)
    else:
        record, created = model.Entry.get_or_create(file_path=relpath, defaults=values)

    if not created:
        record.update(**values).where(model.Entry.id == record.id).execute()

    # Update the entry ID
    del entry['Entry-ID']
    entry['Entry-ID'] = str(record.id)

    if not 'UUID' in entry:
        entry['UUID'] = str(uuid.uuid4())

    # add other relationships to the index
    for alias in entry.get_all('Path-Alias', []):
        path_alias.set_alias(alias, entry=record)

    if fixup_needed:
        tmpfile = fullpath + '.tmp'
        with open(tmpfile, 'w') as file:
            file.write(str(entry))
        os.replace(tmpfile, fullpath)

    return record
