# item.py
# Functions for handling content items

import markdown
import os
import re
import arrow
from enum import Enum

import config

from . import model

class ParseState(Enum):
    HEADERS = 0
    ATF = 1
    BTF = 2

class Entry:
    def __init__(self, fullpath):
        self.headers = {}
        self.body = ''
        self.more = ''

        _,ext = os.path.splitext(fullpath)
        self.markdown = (ext == '.md')

        state = ParseState.HEADERS

        # TODO handle array-type headers (references, tags, etc.)
        # also this code feels really messy
        with open(fullpath, 'r') as file:
            for line in file:
                if state == ParseState.HEADERS:
                    if line.strip():
                        k,_,v = line.partition(': ')
                        if v:
                            self.headers[k.lower()] = v.strip()
                        elif k.strip():
                            # we didn't have any headers but we do have content, so we'd better just treat this as ATF content
                            state = ParseState.ATF
                    else:
                        state = ParseState.ATF

                if state == ParseState.ATF:
                    if line.strip() == '~~~~~':
                        state = ParseState.BTF
                    else:
                        self.body += line
                elif state == ParseState.BTF:
                    self.more += line

    def write_file(self, fullpath):
        with open(fullpath, 'w') as file:
            for k,v in self.headers.items():
                # TODO camelcase the header name
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

def scan_file(fullpath, relpath, assign_id):
    ''' scan a file and put it into the index '''
    entry = Entry(fullpath)

    if not 'id' in entry.headers and not assign_id:
        # We can't operate on this yet
        return False

    fixup_needed = not 'id' in entry.headers or not 'date' in entry.headers

    values = {
        'file_path': fullpath,
        'category': os.path.dirname(relpath),
        'status': model.PublishStatus[entry.headers.get('status', 'PUBLISHED').upper()],
        'entry_type': model.EntryType[entry.headers.get('type', 'ENTRY').upper()],
        'slug_text': entry.headers.get('slug') or make_slug(entry.headers.get('title') or os.path.basename(relpath)),
        'redirect_url': entry.headers.get('redirect-to'),
    }

    entry_id = 'id' in entry.headers and int(entry.headers['id']) or None

    if 'date' in entry.headers:
        entry_date = arrow.get(entry.headers['date'], tzinfo=config.timezone)
    else:
        entry_date = arrow.get(os.stat(fullpath).st_ctime).to(config.timezone)
        entry.headers['date'] = entry_date.format()
    values['entry_date'] = entry_date.datetime

    try:
        # If we have entry_id, use that as the query; otherwise use fullpath
        record = model.Entry.get(
            entry_id and (model.Entry.id == entry_id) or
            (model.Entry.file_path == fullpath))
        record.update(**values).where(model.Entry.id == record.id).execute()
    except model.Entry.DoesNotExist:
        record = model.Entry.create(id=entry_id, **values)

    entry.headers['id'] = record.id

    if fixup_needed:
        entry.write_file(fullpath)

    return record

