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

# TODO this should be the actual class that gets sent along to templates.
# Expected functionality:
# - instance it from an index record (not the fullpath)
# - demand-load from the file when we need something that's not kept in the index
# - body and more are functions that take markdown parameters as arguments
def Entry(fullpath):
    with open(fullpath, 'r') as file:
        entry = email.message_from_file(file)

    # TODO make this split only work when the ~~~~~ is on a single line
    entry.body, _, entry.more = entry.get_payload().partition('~~~~~')

    _,ext = os.path.splitext(fullpath)
    if ext == '.md':
        entry.body = entry.body and markdown.markdown(entry.body)
        entry.more = entry.more and markdown.markdown(entry.more)

    return entry

''' convert a title into a URL-friendly slug '''
def make_slug(title):
    # TODO this should probably handle things other than English ASCII...
    return re.sub(r"[^a-zA-Z0-9]+", r"-", title.strip())

def scan_file(fullpath, relpath, assign_id):
    ''' scan a file and put it into the index '''
    with open(fullpath, 'r') as file:
        entry = email.message_from_file(file)

    entry_id = entry['ID']
    if entry_id == None and not assign_id:
        return False

    fixup_needed = entry_id == None or not 'Date' in entry

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
    del entry['ID']
    entry['ID'] = str(record.id)

    # add other relationships to the index
    for alias in entry.get_all('Path-Alias', []):
        path_alias.set_alias(alias, entry=record)

    if fixup_needed:
        tmpfile = fullpath + '.tmp'
        with open(tmpfile, 'w') as file:
            file.write(str(entry))
        os.replace(tmpfile, fullpath)

    return record
