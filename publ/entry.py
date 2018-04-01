# item.py
# Functions for handling content items

import markdown
import os
import re
import arrow
from enum import Enum
import email

import config

from . import model
from . import path_alias

def Entry(fullpath):
    with open(fullpath, 'r') as file:
        entry = email.message_from_file(file)

    entry.body, _, entry.more = entry.get_payload().partition('~~~~~')

    _,ext = os.path.splitext(fullpath)
    entry.is_markdown = (ext == '.md')

    return entry

''' convert a title into a URL-friendly slug '''
def make_slug(title):
    # TODO this should probably handle things other than English ASCII...
    return re.sub(r"[^a-zA-Z0-9]+", r"-", title.strip())

def scan_file(fullpath, relpath, assign_id):
    ''' scan a file and put it into the index '''
    entry = Entry(fullpath)

    entry_id = entry['ID']
    if entry_id == None and not assign_id:
        return False

    fixup_needed = entry_id == None or not 'Date' in entry

    values = {
        'file_path': fullpath,
        'category': entry.get('Category', os.path.dirname(relpath)),
        'status': model.PublishStatus[entry.get('Status', 'PUBLISHED').upper()],
        'entry_type': model.EntryType[entry.get('Type', 'ENTRY').upper()],
        'slug_text': entry['Slug-Text'] or make_slug(entry.get('Title', os.path.basename(relpath))),
        'redirect_url': entry['Redirect-To'],
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
    del entry['ID']
    entry['ID'] = record.id

    # add other relationships to the index
    for alias in entry.get_all('Path-Alias', []):
        path_alias.set_alias(alias, entry=record)

    if fixup_needed:
        tmpfile = fullpath + '.tmp'
        with open(tmpfile, 'w') as file:
            file.write(entry)
        os.replace(tmpfile, fullpath)

    return record
