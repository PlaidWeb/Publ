# index.py
# Content indexer

import os
import logging
from . import entry
from . import model
import arrow
import watchdog.observers
import watchdog.events
import flask

logger = logging.getLogger(__name__)

ENTRY_TYPES = ['.md', '.htm', '.html']

observer = None
watchdirs = set()

def scan_file(fullpath, relpath, assign_id):
    _,ext = os.path.splitext(fullpath)

    try:
        if ext in ENTRY_TYPES:
            return entry.scan_file(fullpath, relpath, assign_id)

        return True
    except Exception as e:
        logger.exception("Got error parsing %s", fullpath)

def get_last_mtime(fullpath):
    record = model.FileMTime.get_or_none(model.FileMTime.file_path == fullpath)
    if record:
        return record.stat_mtime

def set_last_mtime(fullpath, mtime):
    record, created = model.FileMTime.get_or_create(file_path=fullpath, defaults={'stat_mtime':mtime})
    if not created:
        record.stat_mtime = mtime
        record.save()

class IndexWatchdog(watchdog.events.FileSystemEventHandler):
    def __init__(self, content_dir):
        self.content_dir = content_dir

    def update_file(self, fullpath):
        logger.info("Got update for %s", fullpath)
        relpath = os.path.relpath(fullpath, self.content_dir)

        if scan_file(fullpath, relpath, True):
            logger.info("Updated %s", fullpath)
            set_last_mtime(fullpath, os.stat(fullpath).st_mtime)
        else:
            logger.warning("Couldn't update %s", fullpath)

    def on_created(self, event):
        logger.debug("file created: %s", event.src_path)
        if not event.is_directory:
            self.update_file(event.src_path)

    def on_modified(self, event):
        logger.debug("file modified: %s", event.src_path)
        if not event.is_directory:
            self.update_file(event.src_path)

    def on_moved(self, event):
        logger.debug("file moved: %s -> %s", event.src_path, event.dest_path)
        if not event.is_directory:
            self.update_file(event.dest_path)

    def on_deleted(self, event):
        logger.debug("File deleted: %s", event.src_path)
        if not event.is_directory:
            self.update_file(event.src_path)

def background_scan(content_dir):
    global observer
    global watchdirs

    if not content_dir in watchdirs:
        start_observer = not observer
        if start_observer:
            observer = watchdog.observers.Observer()
        watchdirs.add(content_dir)
        observer.schedule(IndexWatchdog(content_dir), content_dir, recursive=True)
        if start_observer:
            observer.start()

''' scans the specified directory for content to ingest '''
def scan_index(content_dir):
    fixups = []
    for root, _, files in os.walk(content_dir, followlinks=True):
        for file in files:
            basename = file
            fullpath = os.path.join(root, file)
            relpath = os.path.relpath(fullpath, content_dir)

            mtime = os.stat(fullpath).st_mtime
            last_mtime = get_last_mtime(fullpath)
            if not last_mtime or last_mtime < mtime:
                if scan_file(fullpath, relpath, False):
                    logger.info("Scanned %s", fullpath)
                    set_last_mtime(fullpath, mtime)
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
