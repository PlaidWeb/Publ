# item.py
""" Functions for handling content items """

import email
import functools
import hashlib
import logging
import os
import re
import typing
import uuid

import arrow
import flask
from pony import orm
from werkzeug.utils import cached_property

from . import (caching, cards, config, html_entry, links, markdown, model,
               path_alias, queries, tokens, user, utils)
from .utils import CallableProxy, CallableValue, TrueCallableProxy, make_slug

LOGGER = logging.getLogger(__name__)


@functools.lru_cache(10)
def load_message(filepath) -> email.message.Message:
    """ Load a message from the filesystem """
    with open(filepath, 'r', encoding='utf-8') as file:
        return email.message_from_file(file)


class Entry(caching.Memoizable):
    """ A wrapper for an entry. Lazily loads the actual message data when
    necessary.
    """

    # pylint: disable=too-many-instance-attributes,too-many-public-methods

    def __init__(self, record):
        """ Construct an Entry wrapper

        record -- the index record to use as the basis
        """

        LOGGER.debug('init entry %d', record.id)
        self._record = record   # index record

        self._fingerprint = model.FileFingerprint.get(file_path=record.file_path)
        LOGGER.debug('loaded entry %d, fingerprint=%s', record.id, self._fingerprint.fingerprint)

        # maps (section,footnotes_enabled) -> toc/footnote counter
        self._counters: typing.Dict[typing.Tuple[str, bool], markdown.ItemCounter] = {}

    def __lt__(self, other):
        # pylint:disable=protected-access
        return self._record.id < other._record.id

    def _key(self):
        return self._record.id, self._record.file_path, self._fingerprint.fingerprint

    @cached_property
    def date(self) -> arrow.Arrow:
        """ Get the display date of the entry, as an Arrow object """
        return arrow.get(self._record.display_date)

    @cached_property
    def date_year(self) -> str:
        """ Get the entry date' year, useful for grouping """
        return self.date.format(utils.YEAR_FORMAT)

    @cached_property
    def date_month(self) -> str:
        """ Get the entry date's month, useful for grouping """
        return self.date.format(utils.MONTH_FORMAT)

    @cached_property
    def date_day(self) -> str:
        """ Get the entry date's day, useful for grouping """
        return self.date.format(utils.DAY_FORMAT)

    @cached_property
    def link(self) -> typing.Callable[..., str]:
        """ Get a link to this entry. Accepts the same parameters as permalink;
        may be pre-redirected. """
        def _link(*args, **kwargs) -> str:
            """ Returns a link, potentially pre-redirected """
            if self._record.redirect_url:
                return links.resolve(self._record.redirect_url,
                                     self.search_path, kwargs.get('absolute', False))

            return self.permalink(*args, **kwargs)

        return CallableProxy(_link)

    @cached_property
    def permalink(self) -> typing.Callable[..., str]:
        """ Get a canonical link to this entry. Accepts the following parameters:

        absolute -- if True, return an absolute/portable link (default: False)
        expand -- if True, expands the link to include the category and slug text;
            if False, it will only be the entry ID (default: True)
        """
        def _permalink(absolute=False, expand=True, **kwargs) -> str:
            if not self.authorized:
                expand = False
            return flask.url_for('entry',
                                 entry_id=self._record.id,
                                 category=self._record.category if expand else None,
                                 slug_text=self._record.slug_text
                                 if expand and self._record.slug_text
                                 else None,
                                 _external=absolute,
                                 **kwargs)

        return CallableProxy(_permalink)

    @cached_property
    def login(self) -> typing.Callable[..., str]:
        """ Get a link specifically for logging in to the entry. Not intended for general use;
        might be useful for some future authentication flow. """
        def _loginlink(absolute=False, **kwargs) -> str:
            pagelink = flask.url_for('entry', entry_id=self._record.id, **kwargs)
            return flask.url_for('login', redir=pagelink[1:], _external=absolute)
        return CallableProxy(_loginlink)

    @cached_property
    def private(self) -> bool:
        """ Returns True if this post is private, i.e. it is invisible to the logged-out user """
        return not self._record.is_authorized(None)

    @cached_property
    def archive(self) -> typing.Callable[..., str]:
        """ Get a link to this entry in the context of a category template.
        Accepts the following arguments:

        paging -- Which pagination scheme to use; one of:
            day -- the entry date's day
            month -- the entry date's month
            year -- the entry date's year
            offset -- count-based pagination starting at the entry (default)
        tag -- which tag(s) to filter on
        category -- Which category to generate the link against (default: the entry's category)
        template -- Which template to generate the link for
        """
        def _archive_link(paging=None, template='', category=None, absolute=False, tag=None) -> str:
            # pylint:disable=too-many-arguments
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
            elif paging == 'week':
                args['date'] = self.date.span('week')[0].format(utils.WEEK_FORMAT)
            elif paging == 'offset' or not paging:
                args['id'] = self._record.id
            else:
                raise ValueError("Unknown paging type '{}'".format(paging))

            if tag:
                args['tag'] = tag

            return flask.url_for('category', **args, _external=absolute)

        return CallableProxy(_archive_link)

    @cached_property
    def type(self) -> str:
        """ An alias for entry_type """
        return self.entry_type

    @cached_property
    def tags(self) -> typing.List[str]:
        """ Get the original (non-normalized) tags for the entry """
        return self.get_all('Tag')

    @cached_property
    def status(self) -> model.PublishStatus:
        """ Returns a typed version of the entry status """
        return model.PublishStatus(self.status)

    @cached_property
    def next(self) -> typing.Callable[..., typing.Optional["Entry"]]:
        """ Get the next entry in the category, ordered by date.

        Accepts view parameters as arguments.
        """
        def _next(**kwargs) -> typing.Optional["Entry"]:
            """ Get the next item in any particular category """
            spec = self._pagination_default_spec(kwargs)
            spec.update(kwargs)

            query = queries.build_query(spec)
            query = queries.where_after_entry(query, self._record)

            cur_user = user.get_active()
            for record in query.order_by(model.Entry.local_date,
                                         model.Entry.id):
                if record.is_authorized(cur_user):
                    return Entry(record)

                LOGGER.debug("User unauthorized for entry %d", record.id)
                tokens.request(cur_user)
            return None
        return CallableProxy(_next)

    @cached_property
    def previous(self) -> typing.Callable[..., typing.Optional["Entry"]]:
        """ Get the previous entry in the category, ordered by date.

        Accepts view parameters as arguments.
        """
        def _previous(**kwargs) -> typing.Optional["Entry"]:
            """ Get the previous item in any particular category """
            spec = self._pagination_default_spec(kwargs)
            spec.update(kwargs)

            query = queries.build_query(spec)
            query = queries.where_before_entry(query, self._record)

            cur_user = user.get_active()
            for record in query.order_by(orm.desc(model.Entry.local_date),
                                         orm.desc(model.Entry.id)):
                if record.is_authorized(cur_user):
                    return Entry(record)

                LOGGER.debug("User unauthorized for entry %d", record.id)
                tokens.request(cur_user)
            return None
        return CallableProxy(_previous)

    @cached_property
    def category(self):
        """ Get the category this entry belongs to. """
        from .category import Category  # pylint: disable=cyclic-import
        return Category(self._record.category)

    @cached_property
    def title(self) -> typing.Callable[..., str]:
        """ Get the title of the entry. Accepts the following arguments:

        markup -- If True, convert it from Markdown to HTML; otherwise, strip
            all markup (default: True)
        no_smartquotes -- if True, preserve quotes and other characters as originally
            presented
        markdown_extensions -- a list of markdown extensions to use
        always_show -- always show the title even if the current user is not
            authorized to see the entry
        """
        def _title(markup=True, markdown_extensions=None,
                   always_show=False, **kwargs) -> str:
            if not always_show and not self.authorized:
                return ''
            smartquotes = kwargs.get('smartquotes', not kwargs.get('no_smartquotes', False))
            return markdown.render_title(self._record.title, markup, smartquotes,
                                         markdown_extensions)
        return CallableProxy(_title)

    @cached_property
    def search_path(self) -> typing.Tuple[str, ...]:
        """ The relative image search path for this entry """
        return (os.path.dirname(self._record.file_path), self.category.search_path)

    @cached_property
    def _message(self) -> email.message.Message:
        """ get the message payload """
        LOGGER.debug("Loading entry %d from %s", self._record.id, self._record.file_path)
        filepath = self._record.file_path
        try:
            return load_message(filepath)
        except FileNotFoundError:
            expire_file(filepath)
            empty = email.message.Message()
            empty.set_payload('')
            return empty

    @cached_property
    def _entry_content(self) -> typing.Tuple[str, str, bool]:
        if not self.authorized:
            return '', '', False

        body, _, more = self._message.get_payload().partition('\n.....\n')
        if not more and body.startswith('.....\n'):
            # The entry began with a cut, which failed to parse.
            # This rule is easier/faster than dealing with a regex from
            # hell.
            more = body[6:]
            body = ''

        _, ext = os.path.splitext(self._record.file_path)
        is_markdown = ext == '.md'

        return body, more, is_markdown

    @cached_property
    def body(self) -> typing.Callable[..., str]:
        """ Get the above-the-fold entry body text """
        body, _, is_markdown = self._entry_content

        def _body(**kwargs) -> str:
            LOGGER.debug("Rendering body; args=%s", kwargs)

            footnotes: typing.List[str] = []
            tocs: markdown.TocBuffer = []
            body_text = self._get_markup(body, is_markdown, args=kwargs,
                                         footnote_buffer=footnotes,
                                         toc_buffer=tocs)

            self._set_counter('body', kwargs,
                              markdown.ItemCounter(footnote=len(footnotes),
                                                   toc=len(tocs)))

            return body_text

        return TrueCallableProxy(_body) if body else CallableValue('')

    @cached_property
    def more(self) -> typing.Callable[..., str]:
        """ Get the below-the-fold entry body text """
        _, more, is_markdown = self._entry_content

        def _more(**kwargs) -> str:
            LOGGER.debug("Rendering more; kwargs=%s", kwargs)

            body_count = self._get_counter('body', kwargs)
            LOGGER.debug("intro footnotes=%s tocs=%s", body_count.footnote, body_count.toc)

            # pre-fill the buffer with empty entries so the counts are correct
            footnotes = [''] * body_count.footnote

            # pre-fill the buffer with empty entries so the counts are correct
            tocs = [(0, '')] * body_count.toc

            more_text = self._get_markup(more, is_markdown,
                                         footnote_buffer=footnotes,
                                         toc_buffer=tocs,
                                         args=kwargs)

            self._set_counter('more', kwargs,
                              markdown.ItemCounter(footnote=len(footnotes) - body_count.footnote,
                                                   toc=len(tocs) - body_count.toc))

            return more_text

        return TrueCallableProxy(_more) if more else CallableValue('')

    @cached_property
    def footnotes(self) -> typing.Callable[..., str]:
        """ Get the rendered footnotes for the entry """
        body, more, is_markdown = self._entry_content

        def _footnotes(**kwargs) -> str:
            LOGGER.debug("rendering footnotes; args=%s", kwargs)
            return self._get_footnotes(body, more, kwargs)

        if is_markdown:
            body_count = self._counters.get(('body', True))
            more_count = self._counters.get(('more', True))

            if ((body_count and body_count.footnote)
                    or (more_count and more_count.footnote)):
                LOGGER.debug("We definitely have footnotes")
                return TrueCallableProxy(_footnotes)
            if body_count is None or more_count is None:
                LOGGER.debug("We might have footnotes")
                return CallableProxy(_footnotes)

        LOGGER.debug("There are definitely no footnotes")
        return CallableValue('')

    @cached_property
    def toc(self) -> typing.Callable[..., str]:
        """ Get the rendered table of contents for the entry """
        body, more, is_markdown = self._entry_content

        def _toc(max_depth=None, **kwargs) -> str:
            LOGGER.debug("rendering table of contents; max_depth=%s kwargs=%s", max_depth, kwargs)
            return self._get_toc(body, more, max_depth, kwargs)

        if is_markdown:
            body_count = self._counters.get(('body', True))
            more_count = self._counters.get(('more', True))

            if ((body_count and body_count.toc)
                    or (more_count and more_count.toc)):
                LOGGER.debug("We definitely have a ToC")
                return TrueCallableProxy(_toc)

            if body_count is None or more_count is None:
                LOGGER.debug("We might have a ToC")
                return CallableProxy(_toc)

        LOGGER.debug("There is definitely no TOC")
        return CallableValue('')

    @cached_property
    def card(self) -> typing.Callable[..., str]:
        """ Get the entry's OpenGraph card """

        def _get_card(**kwargs) -> str:
            """ Render out the tags for a Twitter/OpenGraph card for this entry. """

            LOGGER.debug("rendering card; args=%s", kwargs)

            def og_tag(key, val) -> str:
                """ produce an OpenGraph tag with the given key and value """
                return utils.make_tag('meta', {'property': key, 'content': val}, start_end=True)

            tags = og_tag('og:title', self.title(markup=False))
            tags += og_tag('og:url', self.link(absolute=True))

            card = self._get_card_data(kwargs)
            for image in card.images[:kwargs.get('count', 1)]:
                tags += og_tag('og:image', image)
            description = self.get('Summary', card.description)
            if description:
                tags += og_tag('og:description', description)

            return flask.Markup(tags)

        return CallableProxy(_get_card)

    def _get_card_data(self, kwargs) -> cards.CardData:
        body, more, is_markdown = self._entry_content

        if body or more:
            footnote: typing.List[str] = []
            toc: markdown.TocBuffer = []
            html_text = self._get_markup(body or more,
                                         is_markdown,
                                         args={'count': 1,
                                               **kwargs,
                                               "max_scale": 1,
                                               "_suppress_footnotes": True,
                                               "absolute": True},
                                         footnote_buffer=footnote,
                                         toc_buffer=toc)

            self._set_counter('body' if body else 'more',
                              kwargs, markdown.ItemCounter(toc=len(toc), footnote=len(footnote)))
        else:
            html_text = ''

        return cards.extract_card(html_text)

    @cached_property
    def summary(self) -> typing.Callable[..., str]:
        """ Get the entry's summary text """

        def _get_summary(**kwargs) -> str:
            """ Render out just the summary """

            summary = self.get('Summary')
            if summary:
                return summary

            card = self._get_card_data(kwargs)
            return flask.Markup((card.description or '').strip())

        return CallableProxy(_get_summary)

    @cached_property
    def last_modified(self) -> arrow.Arrow:
        """ Get the date of last file modification """
        if self.get('Last-Modified'):
            return arrow.get(self.get('Last-Modified'))
        return self.date

    @property
    def authorized(self) -> bool:
        """ Returns if the current user is authorized to see this entry """
        return self._record.is_authorized(user.get_active())

    def _get_markup(self, text, is_markdown, args,
                    footnote_buffer: typing.Optional[list] = None,
                    toc_buffer: typing.Optional[markdown.TocBuffer] = None,
                    postprocess: bool = True) -> str:
        """ get the rendered markup for an entry

            is_markdown -- whether the entry is formatted as Markdown
            kwargs -- parameters to pass to the Markdown processor
        """
        # pylint:disable=too-many-arguments
        if is_markdown:
            if 'footnotes_link' not in args:
                args['footnotes_link'] = self.link(absolute=args.get('absolute'))

            if 'toc_link' not in args:
                args['toc_link'] = self.link(absolute=args.get('absolute'))

            return markdown.to_html(
                text,
                args=args,
                search_path=self.search_path,
                entry_id=self._record.id,
                footnote_buffer=footnote_buffer,
                toc_buffer=toc_buffer,
                postprocess=postprocess
            )

        return html_entry.process(
            text,
            args,
            search_path=self.search_path)

    def _get_footnotes(self, body, more, args) -> str:
        """ get the rendered Markdown footnotes for the entry """
        footnotes: typing.List[str] = []
        if body and self._get_counter('body', args).footnote:
            self._get_markup(body, True, args=args, footnote_buffer=footnotes, postprocess=False)
        if more and self._get_counter('more', args).footnote:
            self._get_markup(more, True, args=args, footnote_buffer=footnotes)

        if footnotes:
            return flask.Markup("<ol>{notes}</ol>".format(notes=''.join(footnotes)))
        return ''

    def _get_toc(self, body, more, max_depth, args) -> str:
        """ get the rendered ToC for the entry """
        tocs: markdown.TocBuffer = []
        args = {**args, '_suppress_footnotes': True}
        if body and self._get_counter('body', args).toc:
            self._get_markup(body, True, args=args, toc_buffer=tocs, postprocess=False)
        if more and self._get_counter('more', args).toc:
            self._get_markup(more, True, args=args, toc_buffer=tocs)

        if tocs:
            return flask.Markup(markdown.toc_to_html(tocs, max_depth))
        return ''

    def _get_counter(self, section, args) -> markdown.ItemCounter:
        """ Count the countables given the specified section and arguments """
        body, more, is_markdown = self._entry_content
        if not is_markdown:
            return markdown.ItemCounter(toc=0, footnote=0)

        footnotes = 'footnotes' in args.get('markdown_extensions', config.markdown_extensions)

        if (section, footnotes) in self._counters:
            return self._counters[(section, footnotes)]

        if section == 'body':
            text = body
        elif section == 'more':
            text = more
        else:
            raise ValueError("Unknown content section " + section)

        if text:
            LOGGER.debug("Getting counters for %s,%s", section, footnotes)
            counter = markdown.get_counters(text, args)
            LOGGER.debug("Caching %s:%s -> %s", section, footnotes, counter)
            self._counters[(section, footnotes)] = counter
            return counter

        return markdown.ItemCounter(toc=0, footnote=0)

    def _set_counter(self, section, args, counter: markdown.ItemCounter):
        """ Register the counts that we already know """
        footnotes = 'footnotes' in args.get('markdown_extensions', config.markdown_extensions)
        LOGGER.debug("Registering %s:%s -> %s", section, footnotes, counter)
        self._counters[(section, footnotes)] = counter

    def __getattr__(self, name):
        """ Proxy undefined properties to the backing objects """

        # Only allow a few vital things for unauthorized access
        if name.lower() not in ('uuid', 'id', 'date', 'last-modified') and not self.authorized:
            return None

        # Don't pass certain things through the database
        if name.lower() not in ('auth') and hasattr(self._record, name):
            return getattr(self._record, name)

        return self._message.get(name)

    def _pagination_default_spec(self, kwargs):
        category = kwargs.get('category', self._record.category)
        return {
            'category': category,
            'recurse': kwargs.get('recurse', 'category' in kwargs)
        }

    def get(self, name, default=None) -> typing.Optional[str]:
        """ Get a single header on an entry """
        return self._message.get(name, default)

    def get_all(self, name) -> typing.List[str]:
        """ Get all related headers on an entry, as an iterable list """
        return self._message.get_all(name) or []

    def __eq__(self, other) -> bool:
        if isinstance(other, int):
            return other == self._record.id
        # pylint:disable=protected-access
        return isinstance(other, Entry) and (other is self or other._record == self._record)


def guess_title(basename) -> str:
    """ Attempt to guess the title from the filename """

    base, _ = os.path.splitext(basename)
    return re.sub(r'[ _-]+', r' ', base).title()


def get_entry_id(entry, fullpath, assign_id) -> typing.Optional[int]:
    """ Get or generate an entry ID for an entry """
    other_entry: typing.Optional[model.Entry] = None

    entry_id: typing.Optional[int] = None
    try:
        entry_id = int(entry['Entry-ID'])
    except (ValueError, KeyError, TypeError) as err:
        LOGGER.debug("Invalid entry-id: %s", err)

    # See if we've inadvertently duplicated an entry ID
    if entry_id is not None:
        try:
            other_entry = model.Entry.get(id=entry_id)
            if (other_entry
                    and os.path.isfile(other_entry.file_path)
                    and not os.path.samefile(other_entry.file_path, fullpath)):
                entry_id = None
            else:
                other_entry = None
        except FileNotFoundError:
            # the other file doesn't exist, so just let it go
            pass

    # Do we need to assign a new ID?
    if not entry_id and not assign_id:
        # We're not assigning IDs yet
        return None

    if not entry_id:
        # See if we already have an entry with this file path
        by_filepath = model.Entry.select(lambda e: e.file_path == fullpath).first()
        if by_filepath:
            entry_id = by_filepath.id

    if not entry_id:
        # We still don't have an ID; generate one pseudo-randomly, based on the
        # entry file path. This approach averages around 0.25 collisions per ID
        # generated while keeping the entry ID reasonably short. In general,
        # count*N averages 1/(N-1) collisions per ID.

        limit = max(10, orm.get(orm.count(e)
                                for e in model.Entry) * 5)  # type:ignore
        attempt = 0
        while not entry_id or model.Entry.get(id=entry_id):
            # Stably generate a quasi-random entry ID from the file path
            md5 = hashlib.md5()
            md5.update("{} {}".format(fullpath, attempt).encode('utf-8'))
            entry_id = int.from_bytes(md5.digest(), byteorder='big') % limit
            attempt = attempt + 1

    if other_entry:
        LOGGER.warning("Entry '%s' had ID %d, which belongs to '%s'. Reassigned to %d",
                       fullpath, other_entry.id, other_entry.file_path, entry_id)

    return entry_id


def save_file(fullpath: str, entry: email.message.Message):
    """ Save a message file out, without mangling the headers """
    from atomicwrites import atomic_write
    with atomic_write(fullpath, overwrite=True) as file:
        # we can't just use file.write(str(entry)) because otherwise the
        # headers "helpfully" do MIME encoding normalization.
        # str(val) is necessary to get around email.header's encoding
        # shenanigans
        for key, val in entry.items():
            print('{}: {}'.format(key, str(val)), file=file)
        print('', file=file)
        file.write(entry.get_payload())


@orm.db_session(retry=5)
def scan_file(fullpath: str, relpath: typing.Optional[str], assign_id: bool) -> bool:
    """ scan a file and put it into the index

    :param fullpath str: The full file path
    :param relpath typing.Optional[str]: The file path relative to the content
        root; if None, this will be inferred
    :param assign_id bool: Whether to assign an ID and fix up the file

    """
    # pylint: disable=too-many-branches,too-many-statements,too-many-locals

    # Since a file has changed, the lrucache is invalid.
    load_message.cache_clear()

    try:
        entry = load_message(fullpath)
    except FileNotFoundError:
        # The file doesn't exist, so remove it from the index
        record = model.Entry.get(file_path=fullpath)
        if record:
            expire_record(record)
        return True

    entry_id = get_entry_id(entry, fullpath, assign_id)
    if entry_id is None:
        return False

    fixup_needed = False

    if not relpath:
        relpath = os.path.relpath(fullpath, config.content_folder)

    basename = os.path.basename(relpath)
    title = entry['title'] or guess_title(basename)

    values = {
        'file_path': fullpath,
        'category': entry.get('Category', utils.get_category(relpath)),
        'status': model.PublishStatus[entry.get('Status', 'SCHEDULED').upper()].value,
        'entry_type': entry.get('Entry-Type', ''),
        'slug_text': make_slug(entry.get('Slug-Text', title)),
        'redirect_url': entry.get('Redirect-To', ''),
        'title': title,
        'sort_title': entry.get('Sort-Title', title),
    }

    entry_date = None
    if 'Date' in entry:
        try:
            entry_date = arrow.get(entry['Date'], tzinfo=config.timezone)
        except arrow.parser.ParserError:
            entry_date = None
    if entry_date is None:
        del entry['Date']
        entry_date = arrow.get(
            os.stat(fullpath).st_ctime).to(config.timezone)
        entry['Date'] = entry_date.format()
        fixup_needed = True

    if 'Last-Modified' in entry:
        last_modified_str = entry['Last-Modified']
        try:
            last_modified = arrow.get(
                last_modified_str, tzinfo=config.timezone)
        except arrow.parser.ParserError:
            last_modified = arrow.get()
            del entry['Last-Modified']
            entry['Last-Modified'] = last_modified.format()
            fixup_needed = True

    values['display_date'] = entry_date.isoformat()
    values['utc_date'] = entry_date.to('utc').datetime
    values['local_date'] = entry_date.naive

    LOGGER.debug("getting entry %s with id %d", fullpath, entry_id)
    record = model.Entry.get(id=entry_id)
    if record:
        LOGGER.debug("Reusing existing entry %d", record.id)
        record.set(**values)
    else:
        record = model.Entry(id=entry_id, **values)

    # Update the entry ID
    if str(record.id) != entry['Entry-ID']:
        del entry['Entry-ID']
        entry['Entry-ID'] = str(record.id)
        fixup_needed = True

    if 'UUID' not in entry:
        entry['UUID'] = str(uuid.uuid5(
            uuid.NAMESPACE_URL, 'file://' + fullpath))
        fixup_needed = True

    # add other relationships to the index
    path_alias.remove_aliases(record)
    if record.visible:
        for alias in entry.get_all('Path-Alias', []):
            path_alias.set_alias(alias, entry=record)

    orm.delete(p for p in model.EntryAuth if p.entry == record)  # type:ignore
    orm.commit()
    for order, user_group in enumerate(entry.get('Auth', '').split()):
        allowed = (user_group[0] != '!')
        if not allowed:
            user_group = user_group[1:]
        model.EntryAuth(order=order, entry=record, user_group=user_group, allowed=allowed)
    orm.commit()

    with orm.db_session:
        set_tags = {
            t.lower()
            for t in entry.get_all('Tag', [])
            + entry.get_all('Hidden-Tag', [])
        }

        for tag in record.tags:
            if tag.key in set_tags:
                set_tags.remove(tag.key)
            else:
                tag.delete()
        for tag in set_tags:
            model.EntryTag(entry=record, key=tag)
        orm.commit()

    if record.status == model.PublishStatus.DRAFT.value:
        LOGGER.info("Not touching draft entry %s", fullpath)
    elif fixup_needed:
        LOGGER.info("Fixing up entry %s", fullpath)
        save_file(fullpath, entry)

    return True


@orm.db_session(retry=5)
def expire_file(filepath):
    """ Expire a record for a missing file """
    load_message.cache_clear()

    # SQLite doesn't support cascading deletes so clean up manually
    orm.delete(pa for pa in model.PathAlias if pa.entry.file_path == filepath)

    orm.delete(item for item in model.Entry if item.file_path == filepath)
    orm.commit()


@orm.db_session(retry=5)
def expire_record(record):
    """ Expire a record for a missing entry """
    load_message.cache_clear()

    # This entry no longer exists so delete it, and anything that references it

    # SQLite doesn't support cascading deletes so let's just clean up
    # manually
    orm.delete(pa for pa in model.PathAlias if pa.entry == record)

    record.delete()
    orm.commit()
