# item.py
# Functions for handling content items

import markdown
import os
import re
import datetime
import dateutil.parser
from enum import Enum

import config

from . import index

class ParseState(Enum):
    HEADERS = 0
    ATF = 1
    BTF = 2

class Entry:
    def __init__(self, fullpath):
        self.headers = {}
        self.body = ''
        self.more = ''

        state = ParseState.HEADERS

        # TODO handle array-type headers (references, tags, etc.)
        # also this code feels really messy
        with open(fullpath, 'r') as file:
            for line in file:
                print("{} {}".format(state,line))
                if state == ParseState.HEADERS:
                    if line.strip():
                        k,_,v = line.partition(': ')
                        self.headers[k.lower()] = v.strip()
                    else:
                        state = ParseState.ATF
                elif state == ParseState.ATF:
                    if line.strip() == '~~~~~':
                        state = ParseState.BTF
                    else:
                        self.body += line
                elif state == ParseState.BTF:
                    self.more += line

    def write_file(self, fullpath):
        with open(fullpath, 'w') as file:
            for k,v in self.headers.items():
                print("{}: {}".format(k, v), file=file)
            print('', file=file)
            print(self.body, file=file)
            if self.more:
                print('~~~~~', file=file)
                print(self.more, file=file)

def make_slug(title):
    ''' convert a title into a URL-friendly slug '''

    # TODO this should probably handle things other than English ASCII...
    return re.sub(r"[^a-zA-Z0-9]+", r"-", title.strip())

def scan_file(fullpath, relpath, assign_id=False):
    ''' scan a file and put it into the index '''

    entry = Entry(fullpath)

    if not 'id' in entry.headers and not assign_id:
        # We can't operate on this yet
        return False

    fixup_needed = not 'id' in entry.headers or not 'date' in entry.headers

    values = {
        'file_path': fullpath,
        'category': os.path.dirname(relpath),
        'status': index.PublishStatus[entry.headers.get('status').upper() or 'PUBLISHED'],
        'type': index.EntryType[entry.headers.get('type').upper() or 'ENTRY'],
        'slug_text': entry.headers.get('slug') or make_slug(entry.headers.get('title') or os.path.basename(relpath)),
        'redirect_url': entry.headers.get('redirect-to'),
    }

    entry_id = 'id' in entry.headers and int(entry.headers['id']) or None

    if 'date' in entry.headers:
        values['date'] = dateutil.parser.parse(entry.headers['date'])
    else:
        values['date'] = datetime.datetime.fromtimestamp(os.stat(fullpath).st_ctime)
        entry.headers['date'] = values['date'].isoformat()

    # Try to get an existing entry for this one
    if entry_id:
        record, created = index.Entry.get_or_create(id=entry_id, defaults=values)
    else:
        record = index.Entry.create(*defaults)
        entry_id = record.id
        entry.headers['id'] = entry_id
        created = True

    if not created:
        # update the database with the newly slurped file
        record.update(**values).where(index.Entry.id == entry_id).execute()

    if fixup_needed:
        entry.write_file(fullpath)

    return True

def scan_index(content_dir):
    ''' scans the specified directory for content to ingest '''
    fixups = []
    for root, _, files in os.walk(content_dir, followlinks=True):
        for file in files:
            basename = file
            fullpath = os.path.join(root, file)
            relpath = os.path.relpath(fullpath, content_dir)
            if not scan_file(fullpath, relpath, assign_id=False):
                # file scan failed, add to the fixups queue
                fixups.append((fullpath, relpath))

    # perform the fixup queue
    for fullpath, relpath in fixups:
        scan_file(fullpath, relpath, assign_id=True)


