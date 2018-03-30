# index.py
# Content indexer

import os
from . import entry

ENTRY_TYPES = ['.md', '.htm', '.html']
IMAGE_TYPES = ['.png', '.gif', '.jpg']

def scan_file(fullpath, relpath, assign_id):
    _,ext = os.path.splitext(fullpath)
    if ext in ENTRY_TYPES:
        return entry.scan_file(fullpath, relpath, assign_id)
    #elif ext in IMAGE_TYPES:
    #   TODO

def scan_index(content_dir):
    ''' scans the specified directory for content to ingest '''
    fixups = []
    for root, _, files in os.walk(content_dir, followlinks=True):
        for file in files:
            basename = file
            fullpath = os.path.join(root, file)
            relpath = os.path.relpath(fullpath, content_dir)
            if not scan_file(fullpath, relpath, False):
                # file scan failed, add to the fixups queue
                fixups.append((fullpath, relpath))

    # perform the fixup queue
    for fullpath, relpath in fixups:
        scan_file(fullpath, relpath, True)


