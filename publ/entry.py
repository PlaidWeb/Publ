# item.py
# Functions for handling content items

import markdown
import os
import re
import arrow
from enum import Enum
from requests.structures import CaseInsensitiveDict

import config

from . import model
from . import path_alias

class ParseState(Enum):
    HEADERS = 0
    WHITESPACE = 1
    ATF = 2
    BTF = 3

class Entry:
    def __init__(self, fullpath):
        self.headers = []
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
                    m = re.match(r'([a-zA-Z0-9\-]+):\s+(.*)$', line)
                    if m:
                        k,v = m.group(1,2)
                        self.headers.append((k,v))
                    else:
                        # We found post-header whitespace to consume
                        state = ParseState.WHITESPACE

                if state == ParseState.WHITESPACE:
                    if line.strip():
                        state = ParseState.ATF

                # ATF processing the BTF marker doesn't fallthrough to BTF parsing
                if state == ParseState.ATF:
                    if line.strip() == '~~~~~':
                        state = ParseState.BTF
                    else:
                        self.body += line
                elif state == ParseState.BTF:
                    self.more += line

    ''' Get the first header matching the given key, case-insensitive '''
    def get_header(self, key, default=None):
        for k,v in self.headers:
            if k.lower() == key.lower():
                return v
        return default

    ''' Get a list of all headers matching the given key '''
    def get_headers(self, key):
        return [v for (k,v) in self.headers if k.lower() == key.lower()]

    ''' Replace the first instance of a header, or set it anew if it doesn't exist

        Returns whether the key was newly-created
    '''
    def set_header(self, key, val):
        for idx,(k,v) in enumerate(self.headers):
            if k.lower() == key.lower():
                self.headers[idx] = (key,val)
                return False
        self.headers.append((k,v))
        return True

    def write_file(self, fullpath):
        with open(fullpath, 'w') as file:
            for k,v in self.headers.items():
                # TODO camelcase the header name
                print("{}: {}".format(k, v), file=file)
            print('', file=file)
            file.write(self.body)
            if self.more:
                print('~~~~~', file=file)
                file.write(self.more)

''' convert a title into a URL-friendly slug '''
def make_slug(title):
    # TODO this should probably handle things other than English ASCII...
    return re.sub(r"[^a-zA-Z0-9]+", r"-", title.strip())

def scan_file(fullpath, relpath, assign_id):
    ''' scan a file and put it into the index '''
    entry = Entry(fullpath)

    entry_id = int(entry.get_header('id') or 0)
    if not entry_id and not assign_id:
        # We can't operate on this yet
        return False

    fixup_needed = not entry_id or not entry.get_header('date')

    values = {
        'file_path': fullpath,
        'category': os.path.dirname(relpath),
        'status': model.PublishStatus[entry.get_header('Status', 'PUBLISHED').upper()],
        'entry_type': model.EntryType[entry.get_header('Type', 'ENTRY').upper()],
        'slug_text': entry.get_header('Slug-Text') or make_slug(entry.get_header('Title') or os.path.basename(relpath)),
        'redirect_url': entry.get_header('Redirect-To'),
    }

    header_date = entry.get_header('Date')
    if header_date:
        entry_date = arrow.get(header_date, tzinfo=config.timezone)
    else:
        entry_date = arrow.get(os.stat(fullpath).st_ctime).to(config.timezone)
    entry.set_header('Date', entry_date.format())
    values['entry_date'] = entry_date.datetime

    try:
        # If we have entry_id, use that as the query; otherwise use fullpath
        record = model.Entry.get(
            entry_id and (model.Entry.id == entry_id) or
            (model.Entry.file_path == fullpath))
        record.update(**values).where(model.Entry.id == record.id).execute()
    except model.Entry.DoesNotExist:
        record = model.Entry.create(id=entry_id, **values)

    entry.set_header('ID', record.id)

    if fixup_needed:
        entry.write_file(fullpath)

    for alias in entry.get_headers("Path-Alias"):
        path_alias.set_alias(alias, entry=record)

    return record

