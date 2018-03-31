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

class ParseState(Enum):
    HEADERS = 0
    WHITESPACE = 1
    ATF = 2
    BTF = 3

class Entry:
    def __init__(self, fullpath):
        self.headers = CaseInsensitiveDict()
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
                        self.headers[k] = v.strip() # TODO handle multiples
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
        'status': model.PublishStatus[entry.headers.get('Status', 'PUBLISHED').upper()],
        'entry_type': model.EntryType[entry.headers.get('Type', 'ENTRY').upper()],
        'slug_text': entry.headers.get('Slug-Text') or make_slug(entry.headers.get('Title') or os.path.basename(relpath)),
        'redirect_url': entry.headers.get('Redirect-To'),
    }

    entry_id = 'ID' in entry.headers and int(entry.headers['ID']) or None

    if 'date' in entry.headers:
        entry_date = arrow.get(entry.headers['date'], tzinfo=config.timezone)
    else:
        entry_date = arrow.get(os.stat(fullpath).st_ctime).to(config.timezone)
        entry.headers['Date'] = entry_date.format()
    values['entry_date'] = entry_date.datetime

    try:
        # If we have entry_id, use that as the query; otherwise use fullpath
        record = model.Entry.get(
            entry_id and (model.Entry.id == entry_id) or
            (model.Entry.file_path == fullpath))
        record.update(**values).where(model.Entry.id == record.id).execute()
    except model.Entry.DoesNotExist:
        record = model.Entry.create(id=entry_id, **values)

    entry.headers['ID'] = record.id

    if fixup_needed:
        entry.write_file(fullpath)

    return record

