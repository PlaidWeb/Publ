# index.py
# Content indexer

import os
import logging
from . import entry

logger = logging.getLogger(__name__)

ENTRY_TYPES = ['.md', '.htm', '.html']
IMAGE_TYPES = ['.png', '.gif', '.jpg']

def scan_file(fullpath, relpath, assign_id):
    _,ext = os.path.splitext(fullpath)

    try:
        if ext in ENTRY_TYPES:
            return entry.scan_file(fullpath, relpath, assign_id)
        #elif ext in IMAGE_TYPES:
        #   TODO
    except Exception as e:
        logger.exception("Got error parsing %s", fullpath)

def scan_index(content_dir):
    ''' scans the specified directory for content to ingest '''
    fixups = []
    for root, _, files in os.walk(content_dir, followlinks=True):
        for file in files:
            basename = file
            fullpath = os.path.join(root, file)
            relpath = os.path.relpath(fullpath, content_dir)

            if scan_file(fullpath, relpath, False):
                logger.info("Scanned %s", fullpath)
            else:
                # file scan failed, add to the fixups queue
                fixups.append((fullpath, relpath))
                logger.info("Scheduling fixup for %s", fullpath)

    # perform the fixup queue
    for fullpath, relpath in fixups:
        if scan_file(fullpath, relpath, True):
            logger.info("Fixed up %s", fullpath)
        else:
            logger.warning("Couldn't fix up %s", fullpath)


