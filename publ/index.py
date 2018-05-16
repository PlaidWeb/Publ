# index.py
''' Content indexer '''

import os
import logging
import concurrent.futures

import watchdog.observers
import watchdog.events

from . import entry
from . import model
from . import utils
from . import category

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name

ENTRY_TYPES = ['.md', '.htm', '.html']
CATEGORY_TYPES = ['.cat', '.meta']

thread_pool = concurrent.futures.ThreadPoolExecutor(  # pylint: disable=invalid-name
    max_workers=1,
    thread_name_prefix="Indexer")


def scan_file(fullpath, relpath, assign_id):
    """ Scan a file for the index

    fullpath -- The full path to the file
    relpath -- The path to the file, relative to its base directory
    assign_id -- Whether to assign an ID to the file if not yet assigned

    This calls into various modules' scanner functions; the expectation is that
    the scan_file function will return a truthy value if it was scanned
    successfully, False if it failed, and None if there is nothing to scan.
    """

    logger.debug("Scanning file: %s (%s) %s", fullpath, relpath, assign_id)

    def do_scan():
        """ helper function to do the scan and gather the result """
        _, ext = os.path.splitext(fullpath)

        try:
            if ext in ENTRY_TYPES:
                logger.info("Scanning entry: %s", fullpath)
                return entry.scan_file(fullpath, relpath, assign_id)

            if ext in CATEGORY_TYPES:
                logger.info("Scanning meta info: %s", fullpath)
                return category.scan_file(fullpath, relpath)

            return None
        except:  # pylint: disable=bare-except
            logger.exception("Got error parsing %s", fullpath)
            return False

    result = do_scan()
    if result is False and not assign_id:
        logger.info("Scheduling fixup for %s", fullpath)
        thread_pool.submit(scan_file, fullpath, relpath, True)
    elif result:
        set_fingerprint(fullpath)


def get_last_fingerprint(fullpath):
    """ Get the last known modification time for a file """
    record = model.FileFingerprint.get_or_none(
        model.FileFingerprint.file_path == fullpath)
    if record:
        return record.fingerprint
    return None


def set_fingerprint(fullpath, fingerprint=None):
    """ Set the last known modification time for a file """
    try:
        fingerprint = fingerprint or utils.file_fingerprint(fullpath)

        record, created = model.FileFingerprint.get_or_create(
            file_path=fullpath, defaults={'fingerprint': fingerprint})
        if not created:
            record.fingerprint = fingerprint
            record.save()
    except FileNotFoundError:
        model.FileFingerprint.delete().where(model.FileFingerprint.file_path == fullpath)


class IndexWatchdog(watchdog.events.PatternMatchingEventHandler):
    """ Watchdog handler """

    def __init__(self, content_dir):
        super().__init__(ignore_directories=True)
        self.content_dir = content_dir

    def update_file(self, fullpath):
        """ Update a file """
        relpath = os.path.relpath(fullpath, self.content_dir)
        thread_pool.submit(scan_file, fullpath, relpath, False)

    def on_created(self, event):
        """ on_created handler """
        logger.info("file created: %s", event.src_path)
        if not event.is_directory:
            self.update_file(event.src_path)

    def on_modified(self, event):
        """ on_modified handler """
        logger.info("file modified: %s", event.src_path)
        if not event.is_directory:
            self.update_file(event.src_path)

    def on_moved(self, event):
        """ on_moved handler """
        logger.info("file moved: %s -> %s", event.src_path, event.dest_path)
        if not event.is_directory:
            self.update_file(event.dest_path)

    def on_deleted(self, event):
        """ on_deleted handler """
        logger.info("File deleted: %s", event.src_path)
        if not event.is_directory:
            self.update_file(event.src_path)


def background_scan(content_dir):
    """ Start background scanning a directory for changes """
    observer = watchdog.observers.Observer()
    observer.schedule(IndexWatchdog(content_dir),
                      content_dir, recursive=True)
    logging.info("Watching %s for changes", content_dir)
    observer.start()


def scan_index(content_dir):
    """ Scan all files in a content directory """

    def scan_directory(root, files):
        """ Helper function to scan a single directory """
        for file in files:
            fullpath = os.path.join(root, file)
            relpath = os.path.relpath(fullpath, content_dir)

            fingerprint = utils.file_fingerprint(fullpath)
            last_fingerprint = get_last_fingerprint(fullpath)
            if fingerprint != last_fingerprint:
                thread_pool.submit(scan_file, fullpath, relpath, False)

    for root, _, files in os.walk(content_dir, followlinks=True):
        thread_pool.submit(scan_directory, root, files)
