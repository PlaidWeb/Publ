# index.py
''' Content indexer '''

import os
import logging
import concurrent.futures
import threading

import watchdog.observers
import watchdog.events
from pony import orm

from . import entry
from . import model
from . import utils
from . import category

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name

ENTRY_TYPES = ['.md', '.htm', '.html']
CATEGORY_TYPES = ['.cat', '.meta']

THREAD_POOL = concurrent.futures.ThreadPoolExecutor(
    max_workers=1,
    thread_name_prefix="Indexer")

# Get the _work_queue attribute from the pool, if any
WORK_QUEUE = getattr(THREAD_POOL, '_work_queue', None)


class ConcurrentSet:
    """ Simple quasi-atomic set """

    def __init__(self):
        self.lock = threading.Lock()
        self.set = set()

    def add(self, item):
        """ Add an item to the set, and return whether it was newly added """
        with self.lock:
            if item in self.set:
                return False
            self.set.add(item)
            return True

    def remove(self, item):
        """ Remove an item from the set, returning if it was present """
        with self.lock:
            if item in self.set:
                self.set.remove(item)
                return True
            return False


SCHEDULED_FILES = ConcurrentSet()


def last_modified():
    """ information about the most recently modified file """
    files = model.FileFingerprint.select().order_by(
        orm.desc(model.FileFingerprint.file_mtime))
    for file in files:
        return file.file_mtime, file.file_path
    return None, None


def queue_length():
    """ Get the approximate length of the indexer work queue """
    return WORK_QUEUE.qsize() if WORK_QUEUE else None


def in_progress():
    """ Return if there's an index in progress """
    return queue_length() > 0


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
        THREAD_POOL.submit(scan_file, fullpath, relpath, True)
    else:
        logger.debug("%s complete", fullpath)
        if result:
            set_fingerprint(fullpath)
        SCHEDULED_FILES.remove(fullpath)


@orm.db_session
def get_last_fingerprint(fullpath):
    """ Get the last known modification time for a file """
    record = model.FileFingerprint.get(file_path=fullpath)
    if record:
        return record.fingerprint
    return None


@orm.db_session(immediate=True)
def set_fingerprint(fullpath, fingerprint=None):
    """ Set the last known modification time for a file """
    try:
        fingerprint = fingerprint or utils.file_fingerprint(fullpath)

        record = model.FileFingerprint.get(file_path=fullpath)
        if record:
            record.set(fingerprint=fingerprint,
                       file_mtime=os.stat(fullpath).st_mtime)
        else:
            record = model.FileFingerprint(
                file_path=fullpath,
                fingerprint=fingerprint,
                file_mtime=os.stat(fullpath).st_mtime)
        orm.commit()
    except FileNotFoundError:
        orm.delete(fp for fp in model.FileFingerprint if fp.file_path == fullpath)


class IndexWatchdog(watchdog.events.PatternMatchingEventHandler):
    """ Watchdog handler """

    def __init__(self, content_dir):
        super().__init__(ignore_directories=True)
        self.content_dir = content_dir

    def update_file(self, fullpath):
        """ Update a file """
        if SCHEDULED_FILES.add(fullpath):
            logger.debug("Scheduling reindex of %s", fullpath)
            relpath = os.path.relpath(fullpath, self.content_dir)
            THREAD_POOL.submit(scan_file, fullpath, relpath, False)

    def on_created(self, event):
        """ on_created handler """
        logger.debug("file created: %s", event.src_path)
        if not event.is_directory:
            self.update_file(event.src_path)

    def on_modified(self, event):
        """ on_modified handler """
        logger.debug("file modified: %s", event.src_path)
        if not event.is_directory:
            self.update_file(event.src_path)

    def on_moved(self, event):
        """ on_moved handler """
        logger.debug("file moved: %s -> %s", event.src_path, event.dest_path)
        if not event.is_directory:
            self.update_file(event.dest_path)

    def on_deleted(self, event):
        """ on_deleted handler """
        logger.debug("File deleted: %s", event.src_path)
        if not event.is_directory:
            self.update_file(event.src_path)


def background_scan(content_dir):
    """ Start background scanning a directory for changes """
    observer = watchdog.observers.Observer()
    observer.schedule(IndexWatchdog(content_dir),
                      content_dir, recursive=True)
    logging.info("Watching %s for changes", content_dir)
    observer.start()


@orm.db_session(immediate=True)
def prune_missing(table):
    """ Prune any files which are missing from the specified table """
    try:
        for item in table.select():
            if not os.path.isfile(item.file_path):
                logger.info("File disappeared: %s", item.file_path)
                item.delete()
    except:  # pylint:disable=bare-except
        logger.exception("Error pruning %s", table)


def scan_index(content_dir):
    """ Scan all files in a content directory """

    def scan_directory(root, files):
        """ Helper function to scan a single directory """
        try:
            for file in files:
                fullpath = os.path.join(root, file)
                relpath = os.path.relpath(fullpath, content_dir)

                fingerprint = utils.file_fingerprint(fullpath)
                last_fingerprint = get_last_fingerprint(fullpath)
                if fingerprint != last_fingerprint and SCHEDULED_FILES.add(fullpath):
                    scan_file(fullpath, relpath, False)
        except:  # pylint:disable=bare-except
            logger.exception("Got error parsing directory %s", root)

    for root, _, files in os.walk(content_dir, followlinks=True):
        THREAD_POOL.submit(scan_directory, root, files)

    for table in (model.Entry, model.Category, model.Image, model.FileFingerprint):
        THREAD_POOL.submit(prune_missing, table)
