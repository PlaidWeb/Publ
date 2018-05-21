# item.py
""" Functions for handling content items """

from __future__ import absolute_import, with_statement

import email
import functools
import logging
import os
import random
import re
import shutil
import tempfile
import uuid

import arrow
import flask
from werkzeug.utils import cached_property

from . import config
from . import model
from . import queries
from . import path_alias
from . import markdown
from . import utils
from . import cards
from .utils import CallableProxy, TrueCallableProxy, make_slug

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


@functools.lru_cache(10)
def load_message(filepath):
    """ Load a message from the filesystem """
    with open(filepath, 'r') as file:
        return email.message_from_file(file)


class Entry:
    """ A wrapper for an entry. Lazily loads the actual message data when
    necessary.
    """

    # pylint: disable=too-many-instance-attributes

    def __init__(self, record):
        """ Construct an Entry wrapper

        record -- the index record to use as the basis
        """

        self._record = record   # index record
        self._message = None    # actual message payload, lazy-loaded

        self.date = arrow.get(record.display_date)

        self.link = CallableProxy(self._link)
        self.permalink = CallableProxy(self._permalink)
        self.archive = CallableProxy(self._archive_link)

        self.next = CallableProxy(self._next)
        self.previous = CallableProxy(self._previous)

        from .category import Category  # pylint: disable=cyclic-import
        self.category = Category(record.category)

    def _link(self, *args, **kwargs):
        """ Returns a link, potentially pre-redirected """
        if self._record.redirect_url:
            return self._record.redirect_url

        return self._permalink(*args, **kwargs)

    def _permalink(self, absolute=False, expand=True):
        """ Returns a canonical URL for the item """
        return flask.url_for('entry',
                             entry_id=self._record.id,
                             category=self._record.category if expand else None,
                             slug_text=self._record.slug_text if expand else None,
                             _external=absolute)

    def _archive_link(self, paging=None, template='', category=None, absolute=False):
        args = {
            'template': template,
            'category': category if category is not None else self.category,
        }
        if paging == 'day':
            args['date'] = self.date.format(utils.DAY_FORMAT)
        elif paging == 'month':
            args['date'] = self.date.format(utils.MONTH_FORMAT)
        elif paging == 'year':
            args['date'] = self.date.format(utils.YEAR_FORMAT)
        else:
            args['start'] = self._record.id

        return flask.url_for('category', **args, _external=absolute)

    @cached_property
    def image_search_path(self):
        """ The relative image search path for this entry """
        return [os.path.dirname(self._record.file_path)] + self.category.image_search_path

    def _load(self):
        """ ensure the message payload is loaded """
        # pylint: disable=attribute-defined-outside-init

        if not self._message:
            filepath = self._record.file_path
            try:
                self._message = load_message(filepath)
            except FileNotFoundError:
                expire_record(self._record)

            body, _, more = self._message.get_payload().partition('\n.....\n')
            if not more and body.startswith('.....\n'):
                # The entry began with a cut, which failed to parse.
                # This rule is easier/faster than dealing with a regex from
                # hell.
                more = body[6:]
                body = ''

            _, ext = os.path.splitext(filepath)
            is_markdown = ext == '.md'
            self.body = TrueCallableProxy(
                self._get_markup,
                body,
                is_markdown) if body else CallableProxy(None)
            self.more = TrueCallableProxy(
                self._get_markup,
                more,
                is_markdown) if more else CallableProxy(None)

            self.last_modified = arrow.get(
                os.stat(self._record.file_path).st_mtime).to(config.timezone)

            self.card = TrueCallableProxy(
                self._get_card,
                body or more) if is_markdown else CallableProxy(None)

            return True
        return False

    def _get_markup(self, text, is_markdown, **kwargs):
        """ get the rendered markup for an entry

            is_markdown -- whether the entry is formatted as Markdown
            kwargs -- parameters to pass to the Markdown processor
        """
        if is_markdown:
            return flask.Markup(markdown.to_html(
                text,
                config=kwargs,
                image_search_path=self.image_search_path))
        return flask.Markup(text)

    def _get_card(self, text, **kwargs):
        """ Render out the tags for a Twitter/OpenGraph card for this entry. """

        def og_tag(key, val):
            """ produce an OpenGraph tag with the given key and value """
            return utils.make_tag('meta', {'property': key, 'content': val}, start_end=True)

        tags = og_tag('og:title', self.title)
        tags += og_tag('og:url', self.link(absolute=True))

        card = cards.extract_card(text, kwargs, self.image_search_path)
        for image in card.images:
            tags += og_tag('og:image', image)
        if card.description:
            tags += og_tag('og:description', card.description)

        return flask.Markup(tags)

    def __getattr__(self, name):
        """ Proxy undefined properties to the backing objects """

        if hasattr(self._record, name):
            return getattr(self._record, name)

        if self._load():
            # We just loaded which modifies our own attrs, so rerun the default
            # logic
            return getattr(self, name)

        return self._message.get(name)

    @staticmethod
    def _get_first(query):
        """ Get the first entry in a query result """
        query = query.limit(1)
        return Entry(query[0]) if query.count() else None

    def _pagination_default_spec(self, kwargs):
        category = kwargs.get('category', self._record.category)
        return {
            'category': category,
            'recurse': kwargs.get('recurse', category != self._record.category)
        }

    def _previous(self, **kwargs):
        """ Get the previous item in any particular category """
        spec = self._pagination_default_spec(kwargs)
        spec.update(kwargs)

        return self._get_first(model.Entry.select().where(
            queries.build_query(spec) &
            queries.where_before_entry(self._record)
        ).order_by(-model.Entry.local_date, -model.Entry.id))

    def _next(self, **kwargs):
        """ Get the next item in any particular category """
        spec = self._pagination_default_spec(kwargs)
        spec.update(kwargs)

        return self._get_first(
            model.Entry.select().where(
                queries.build_query(spec) &
                queries.where_after_entry(self._record)
            ).order_by(model.Entry.local_date, model.Entry.id))

    def get(self, name, default=None):
        """ Get a single header on an entry """

        self._load()
        return self._message.get(name, default)

    def get_all(self, name):
        """ Get all related headers on an entry, as an iterable list """
        self._load()
        return self._message.get_all(name) or []


def guess_title(basename):
    """ Attempt to guess the title from the filename """

    base, _ = os.path.splitext(basename)
    return re.sub(r'[ _-]+', r' ', base).title()


def get_entry_id(entry, fullpath, assign_id):
    """ Get or generate an entry ID for an entry """
    warn_duplicate = False

    if 'Entry-ID' in entry:
        entry_id = int(entry['Entry-ID'])
    else:
        entry_id = None

    # See if we've inadvertently duplicated an entry ID
    if entry_id:
        other_entry = model.Entry.get_or_none(model.Entry.id == entry_id)
        if (other_entry
                and other_entry.file_path != fullpath
                and os.path.isfile(other_entry.file_path)):
            warn_duplicate = entry_id
            entry_id = None

    # Do we need to assign a new ID?
    if not entry_id and not assign_id:
        # We're not assigning IDs yet
        return None

    if not entry_id:
        # See if we already have an entry with this file path
        by_filepath = model.Entry.get_or_none(file_path=fullpath)
        if by_filepath:
            entry_id = by_filepath.id

    if not entry_id:
        # We still don't have an ID; generate one randomly. Experiments find that this approach
        # averages around 0.25 collisions per ID generated while keeping the
        # entry ID reasonably short. count*N+C averages 1/(N-1) collisions
        # per ID.

        # database=None is to shut up pylint
        limit = max(10, model.Entry.select().count(database=None) * 5)

        entry_id = random.randint(1, limit)
        while model.Entry.get_or_none(model.Entry.id == entry_id):
            entry_id = random.randint(1, limit)

    if warn_duplicate is not False:
        logger.warning("Entry '%s' had ID %d, which belongs to '%s'. Reassigned to %d",
                       fullpath, warn_duplicate, other_entry.file_path, entry_id)

    return entry_id


def save_file(fullpath, entry):
    """ Save a message file out, without mangling the headers """
    with tempfile.NamedTemporaryFile('w', delete=False) as file:
        tmpfile = file.name
        # we can't just use file.write(str(entry)) because otherwise the
        # headers "helpfully" do MIME encoding normalization.
        # str(val) is necessary to get around email.header's encoding
        # shenanigans
        for key, val in entry.items():
            print('{}: {}'.format(key, str(val)), file=file)
        print('', file=file)
        file.write(entry.get_payload())
    shutil.move(tmpfile, fullpath)


def scan_file(fullpath, relpath, assign_id):
    """ scan a file and put it into the index """

    # Since a file has changed, the lrucache is invalid.
    load_message.cache_clear()

    try:
        entry = load_message(fullpath)
    except FileNotFoundError:
        # The file doesn't exist, so remove it from the index
        record = model.Entry.get_or_none(file_path=fullpath)
        if record:
            expire_record(record)
        return True

    with model.lock:
        entry_id = get_entry_id(entry, fullpath, assign_id)
        if entry_id is None:
            return False

        fixup_needed = (str(entry_id) != entry.get('Entry-ID')
                        or 'Date' not in entry
                        or 'UUID' not in entry)

        basename = os.path.basename(relpath)
        title = entry['title'] or guess_title(basename)

        values = {
            'file_path': fullpath,
            'category': entry.get('Category', os.path.dirname(relpath)),
            'status': model.PublishStatus[entry.get('Status', 'SCHEDULED').upper()],
            'entry_type': entry.get('Entry-Type', ''),
            'slug_text': make_slug(entry['Slug-Text'] or title),
            'redirect_url': entry['Redirect-To'],
            'title': title,
        }

        if 'Date' in entry:
            entry_date = arrow.get(entry['Date'], tzinfo=config.timezone)
            del entry['Date']
            entry['Date'] = entry_date.format()
        else:
            entry_date = arrow.get(
                os.stat(fullpath).st_ctime).to(config.timezone)
            entry['Date'] = entry_date.format()

        values['display_date'] = entry_date.datetime
        values['utc_date'] = entry_date.to('utc').datetime
        values['local_date'] = entry_date.naive

        logger.debug("getting entry %s with id %d", fullpath, entry_id)
        record, created = model.Entry.get_or_create(
            id=entry_id, defaults=values)

        if not created:
            logger.debug("Reusing existing entry %d", record.id)
            record.update(**values).where(model.Entry.id ==
                                          record.id).execute()

        # Update the entry ID
        del entry['Entry-ID']
        entry['Entry-ID'] = str(record.id)

        if not 'UUID' in entry:
            entry['UUID'] = str(uuid.uuid4())

        # add other relationships to the index
        for alias in entry.get_all('Path-Alias', []):
            path_alias.set_alias(alias, entry=record)
        for alias in entry.get_all('Path-Unalias', []):
            path_alias.remove_alias(alias)

        if fixup_needed:
            save_file(fullpath, entry)

        return record


def expire_record(record):
    """ Expire a record for a missing entry """
    load_message.cache_clear()

    with model.lock:
        # This entry no longer exists so delete it, and anything that references it
        # SQLite doesn't support cascading deletes so let's just clean up
        # manually
        model.PathAlias.delete().where(model.PathAlias.entry == record).execute()
        record.delete_instance(recursive=True)
