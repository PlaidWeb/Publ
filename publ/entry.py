""" Functions for handling content items """

import datetime
import email
import hashlib
import logging
import os
import typing
import uuid

import arrow
import flask
import slugify
from pony import orm
from werkzeug.utils import cached_property

from . import (caching, cards, html_entry, links, markdown, model, path_alias,
               queries, tokens, user, utils)
from .config import config
from .utils import CallableProxy, CallableValue, TrueCallableProxy

LOGGER = logging.getLogger(__name__)


def load_message(filepath) -> email.message.Message:
    """ Load a message from the filesystem """
    with open(filepath, 'r', encoding='utf-8') as file:
        return email.message_from_file(file)


class Entry(caching.Memoizable):
    """ A wrapper for an entry. Lazily loads the actual message data when
    necessary.
    """

    # pylint: disable=too-many-instance-attributes,too-many-public-methods

    __hash__ = caching.Memoizable.__hash__  # type:ignore

    @staticmethod
    @utils.stash
    def load(record: model.Entry):
        """ Get a pooled Entry wrapper

        record -- the index record to use as the basis
        """
        return Entry(Entry.load.__name__, record)

    def __init__(self, create_key, record) -> None:
        """ Instantiate the Entry wrapper """

        assert create_key == Entry.load.__name__, "Entry must be created with Entry.load()"

        self._record = record   # index record
        self._fingerprint = model.FileFingerprint.get(file_path=record.file_path)
        LOGGER.debug('loaded entry %d, fingerprint=%s', record.id,
                     self._fingerprint.fingerprint if self._fingerprint else None)

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

            if self._record.canonical_path:
                # This is a hack that assumes that the standard '/<template>'
                # rule is in effect. This will have to change if we implement
                # https://github.com/PlaidWeb/Publ/issues/286
                return flask.url_for('category',
                                     template=self._record.canonical_path,
                                     _external=absolute)

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
                raise ValueError(f"Unknown paging type '{paging}'")

            if tag:
                args['tag'] = list(utils.TagSet(utils.as_list(tag)).keys())

            return flask.url_for('category', **args, _external=absolute)

        return CallableProxy(_archive_link)

    @cached_property
    def type(self) -> str:
        """ An alias for entry_type """
        return self.entry_type

    @cached_property
    def tags(self) -> typing.List[str]:
        """ Get the original (non-normalized, non-folded) tags for the entry """
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
                    return Entry.load(record)

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
                    return Entry.load(record)

                LOGGER.debug("User unauthorized for entry %d", record.id)
                tokens.request(cur_user)
            return None
        return CallableProxy(_previous)

    @cached_property
    def category(self):
        """ Get the category this entry belongs to. """
        from .category import Category  # pylint: disable=cyclic-import
        return Category.load(self._record.category)

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
        return TrueCallableProxy(_title) if self._record.title else CallableValue('')

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
            expire_record(self._record)
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

            counter = markdown.ItemCounter()
            body_text = self._get_markup(body, is_markdown, args=kwargs,
                                         footnote_buffer=footnotes,
                                         toc_buffer=tocs,
                                         counter=counter)

            self._set_counter('body', kwargs, counter)

            return body_text

        return TrueCallableProxy(_body) if body else CallableValue('')

    @cached_property
    def more(self) -> typing.Callable[..., str]:
        """ Get the below-the-fold entry body text """
        _, more, is_markdown = self._entry_content

        def _more(**kwargs) -> str:
            LOGGER.debug("Rendering more; kwargs=%s", kwargs)

            body_count = self._get_counter('body', kwargs)
            LOGGER.debug("intro footnotes=%d tocs=%d codeblocks=%d",
                         body_count.footnote, body_count.toc, body_count.code_blocks)

            counter = body_count.copy()
            more_text = self._get_markup(more, is_markdown,
                                         args=kwargs,
                                         counter=counter)

            self._set_counter('more', kwargs, counter)

            return more_text

        return TrueCallableProxy(_more) if more else CallableValue('')

    @cached_property
    def footnotes(self) -> typing.Callable[..., str]:
        """ Get the rendered footnotes for the entry """
        body, more, is_markdown = self._entry_content

        def _footnotes(**kwargs) -> str:
            return self._get_footnotes(body, more, kwargs)

        if is_markdown:
            body_count = self._counters.get(('body', True))
            more_count = self._counters.get(('more', True))

            if ((body_count and body_count.footnote)
                    or (more_count and more_count.footnote)):
                return TrueCallableProxy(_footnotes)
            if body_count is None or more_count is None:
                return CallableProxy(_footnotes)

        return CallableValue('')

    @cached_property
    def toc(self) -> typing.Callable[..., str]:
        """ Get the rendered table of contents for the entry """
        body, more, is_markdown = self._entry_content

        def _toc(max_depth=None, **kwargs) -> str:
            return self._get_toc(body, more, max_depth, kwargs)

        if is_markdown:
            body_count = self._counters.get(('body', True))
            more_count = self._counters.get(('more', True))

            if ((body_count and body_count.toc)
                    or (more_count and more_count.toc)):
                return TrueCallableProxy(_toc)

            if body_count is None or more_count is None:
                return CallableProxy(_toc)

        return CallableValue('')

    @cached_property
    def card(self) -> typing.Callable[..., str]:
        """ Get the entry's OpenGraph card """

        def _get_card(**kwargs) -> str:
            """ Render out the tags for a Twitter/OpenGraph card for this entry. """

            def og_tag(key, val) -> str:
                """ produce an OpenGraph tag with the given key and value """
                return utils.make_tag('meta', {'property': key, 'content': val}, start_end=True)

            tags = og_tag('og:title', self.title(markup=False))
            tags += og_tag('og:url', self.link(absolute=True))

            body, more, is_markdown = self._entry_content
            html_text = self._get_markup(body + '\n\n' + more,
                                         is_markdown,
                                         args={'count': 1,
                                               **kwargs,
                                               "max_scale": 1,
                                               "_suppress_footnotes": True,
                                               "_no_resize_external": True,
                                               "absolute": True},
                                         counter=markdown.ItemCounter())
            card = cards.extract_card(html_text)

            for (image, width, height) in card.images[:kwargs.get('count', 1)]:
                tags += og_tag('og:image', image)
                if width:
                    tags += og_tag('og:image:width', width)
                if height:
                    tags += og_tag('og:image:height', height)

            description = self.summary(markup=False)
            if description:
                tags += og_tag('og:description', description)

            return flask.Markup(tags)

        return CallableProxy(_get_card)

    @cached_property
    def summary(self) -> typing.Callable[..., str]:
        """ Get the summary of the entry, falling back to the first paragraph if
        not present. Accepts the following arguments:

        markup -- If True, convert it from Markdown to HTML; otherwise, strip
            all markup (default: True)
        no_smartquotes -- if True, preserve quotes and other characters as originally
            presented
        markdown_extensions -- a list of markdown extensions to use
        always_show -- always show the title even if the current user is not
            authorized to see the entry
        """
        def _summary(markup=True, markdown_extensions=None,
                     always_show=False, **kwargs) -> str:
            if not always_show and not self.authorized:
                return ''

            summary = self.get('Summary')
            if summary:
                smartquotes = kwargs.get('smartquotes', not kwargs.get('no_smartquotes', False))
                return markdown.render_title(summary, markup, smartquotes,
                                             markdown_extensions)

            # We don't have a declared summary, so derive it from the first text paragraph
            body, more, is_markdown = self._entry_content

            if body or more:
                html_text = self._get_markup(body or more,
                                             is_markdown,
                                             args={**kwargs,
                                                   "max_scale": 1,
                                                   "_suppress_images": True,
                                                   "_suppress_footnotes": True,
                                                   "_no_resize_external": True,
                                                   "absolute": True},
                                             counter=markdown.ItemCounter())
                html_text = html_entry.first_paragraph(html_text)
                if markup:
                    return flask.Markup(html_text)

                return html_entry.strip_html(
                    html_text,
                    remove_elements=markdown.PLAINTEXT_REMOVE_ELEMENTS)

            return ''

        return CallableProxy(_summary)

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
                    counter: markdown.ItemCounter,
                    footnote_buffer: typing.Optional[list] = None,
                    toc_buffer: typing.Optional[markdown.TocBuffer] = None,
                    postprocess: bool = True) -> str:
        """ get the rendered markup for an entry

            is_markdown -- whether the entry is formatted as Markdown
            kwargs -- parameters to pass to the Markdown processor
        """
        # pylint:disable=too-many-arguments
        if is_markdown:
            # Set defaults for the ID link generators, so permalinks from category
            # pages work correctly
            default_link = self.link(absolute=args.get('absolute'))
            for link_flag in ('footnotes_link', 'toc_link', 'code_number_links'):
                if link_flag not in args or args[link_flag] is True:
                    args[link_flag] = default_link

            return markdown.to_html(
                text,
                args=args,
                search_path=self.search_path,
                entry_id=self._record.id,
                footnote_buffer=footnote_buffer,
                toc_buffer=toc_buffer,
                postprocess=postprocess,
                counter=counter
            )

        text = html_entry.process(
            text,
            args,
            search_path=self.search_path)

        if not args.get('markup', True):
            text = html_entry.strip_html(text)

        return text

    @cached_property
    def attachments(self) -> typing.Callable[..., typing.List]:
        """ Returns a view of entries that are attached to this one. Takes the
        standard view arguments. """

        def _get_attachments(order=None, **kwargs) -> typing.List:
            query = queries.build_query({**kwargs,
                                         'attachments': self._record
                                         })
            if order:
                query = query.order_by(*queries.ORDER_BY[order])
            cur_user = user.get_active()

            return [Entry.load(e) for e in query
                    if e.is_authorized(cur_user) or tokens.request(cur_user)]

        return CallableProxy(_get_attachments)

    @cached_property
    def attached(self) -> typing.Callable[..., typing.List]:
        """ Get all the entries that have attached this one """

        def _get_attached(order=None, **kwargs) -> typing.List:
            query = queries.build_query({**kwargs,
                                         'attached': self._record
                                         })
            if order:
                query = query.order_by(*queries.ORDER_BY[order])
            return [Entry.load(e) for e in query]

        return CallableProxy(_get_attached)

    def _get_footnotes(self, body, more, args) -> str:
        """ get the rendered Markdown footnotes for the entry """
        footnotes: typing.List[str] = []
        counter = markdown.ItemCounter()
        if body and self._get_counter('body', args).footnote:
            self._get_markup(body, True, args=args,
                             footnote_buffer=footnotes,
                             postprocess=False,
                             counter=counter)
        if more and self._get_counter('more', args).footnote:
            self._get_markup(more, True, args=args,
                             footnote_buffer=footnotes,
                             counter=counter)

        if footnotes:
            return flask.Markup(f"<ol>{''.join(footnotes)}</ol>")
        return ''

    def _get_toc(self, body, more, max_depth, args) -> str:
        """ get the rendered ToC for the entry """
        tocs: markdown.TocBuffer = []
        args = {**args, '_suppress_footnotes': True}
        counter = markdown.ItemCounter()
        if body and self._get_counter('body', args).toc:
            self._get_markup(body, True, args=args, toc_buffer=tocs, postprocess=False,
                             counter=counter)
        if more and self._get_counter('more', args).toc:
            self._get_markup(more, True, args=args, toc_buffer=tocs, counter=counter)

        if tocs:
            return flask.Markup(markdown.toc_to_html(tocs, max_depth))
        return ''

    def _get_counter(self, section, args) -> markdown.ItemCounter:
        """ Count the countables given the specified section and arguments """
        body, more, is_markdown = self._entry_content
        if not is_markdown:
            return markdown.ItemCounter()

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
            counter = markdown.get_counters(text, args)
            self._counters[(section, footnotes)] = counter
            return counter

        return markdown.ItemCounter()

    def _set_counter(self, section, args, counter: markdown.ItemCounter):
        """ Register the counts that we already know """
        footnotes = 'footnotes' in args.get('markdown_extensions', config.markdown_extensions)
        self._counters[(section, footnotes)] = counter

    def _authorized_attr(self, name):
        """ Return whether an attribute is authorized to be read """
        return name.lower() in ('uuid', 'id', 'date', 'last-modified') or self.authorized

    def __getattr__(self, name):
        """ Proxy undefined properties to the backing objects """

        # Only allow a few vital things for unauthorized access
        if not self._authorized_attr(name):
            return None

        # Don't pass certain things through the database
        if name.lower() not in ('auth') and hasattr(self._record, name):
            return getattr(self._record, name)

        return self._message.get(name)

    def _pagination_default_spec(self, kwargs):
        category = kwargs.get('category', self._record.category)
        return {
            'category': category,
        }

    def get(self, name, default=None, always_show=False) -> typing.Optional[str]:
        """ Get a single header on an entry """
        if always_show or self._authorized_attr(name):
            return self._message.get(name, default)
        return None

    def get_all(self, name, always_show=False) -> typing.List[str]:
        """ Get all related headers on an entry, as an iterable list """
        if always_show or self._authorized_attr(name):
            values = self._message.get_all(name)
            return [str(item) for item in values] if values else []
        return []

    def __eq__(self, other) -> bool:
        if isinstance(other, int):
            return other == self._record.id
        # pylint:disable=protected-access
        return isinstance(other, Entry) and (other is self or other._record == self._record)

    @staticmethod
    def filter_auth(entries, count=None, unauthorized=0) -> typing.List['Entry']:
        """ Filter a list of entries based on authorization, with a maximum
        unauthorized entry count """

        result: typing.List[Entry] = []
        cur_user = user.get_active()
        for record in entries:
            if count is not None and len(result) >= count:
                break

            auth = record.is_authorized(cur_user)
            if auth or unauthorized:
                result.append(Entry.load(record))
                if not auth and unauthorized is not True:
                    unauthorized -= 1

            if not auth:
                tokens.request(cur_user)

        return result


def get_entry_id(entry, fullpath, assign_id) -> typing.Optional[int]:
    """ Get or generate an entry ID for an entry """
    other_entry: typing.Optional[model.Entry] = None

    try:
        entry_id = int(entry['Entry-ID']) if 'Entry-ID' in entry else None
    except (ValueError, KeyError, TypeError) as err:
        LOGGER.debug("Invalid entry-id: %s", err)

    # See if we've inadvertently duplicated an entry ID
    if entry_id is not None:
        try:
            other_entry = model.Entry.get(id=entry_id)
            if (other_entry
                    and os.path.isfile(other_entry.file_path)
                    and not os.path.samefile(other_entry.file_path, fullpath)
                    and other_entry.status != model.PublishStatus.DRAFT.value):
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
            md5.update(f"{fullpath} {attempt}".encode('utf-8'))
            entry_id = int.from_bytes(md5.digest(), byteorder='big') % limit
            attempt = attempt + 1

    if other_entry:
        LOGGER.warning("Entry '%s' had ID %d, which belongs to '%s'. Reassigned to %d",
                       fullpath, other_entry.id, other_entry.file_path, entry_id)

    return entry_id


def save_file(fullpath: str, entry: email.message.Message, fingerprint: str):
    """ Save a message file out, without mangling the headers """
    from atomicwrites import atomic_write
    with atomic_write(fullpath, overwrite=True) as file:
        # we can't just use file.write(str(entry)) because otherwise the
        # headers "helpfully" do MIME encoding normalization.
        # str(val) is necessary to get around email.header's encoding
        # shenanigans
        for key, val in entry.items():
            print(f'{key}: {str(val)}', file=file)
        print('', file=file)
        file.write(entry.get_payload())

        if utils.file_fingerprint(fullpath) != fingerprint:
            LOGGER.warning("File %s changed during atomic write; aborting", fullpath)
            raise RuntimeError("File changed during reindex")

    return True


@orm.db_session(retry=5)
def scan_file(fullpath: str, relpath: typing.Optional[str], fixup_pass: int) -> bool:
    """ scan a file and put it into the index

    :param fullpath str: The full file path
    :param relpath typing.Optional[str]: The file path relative to the content
        root; if None, this will be inferred
    :param fixup_pass int: Which iteration of fixing-up we're on

    """
    # pylint: disable=too-many-branches,too-many-statements,too-many-locals
    from .flask_wrapper import current_app

    try:
        check_fingerprint = utils.file_fingerprint(fullpath)
        entry = load_message(fullpath)
    except FileNotFoundError:
        # The file doesn't exist, so remove it from the index
        record = model.Entry.get(file_path=fullpath)
        if record:
            expire_record(record)
        return True

    entry_id = get_entry_id(entry, fullpath, fixup_pass > 0)
    if entry_id is None:
        return False

    fixup_needed = False

    if not relpath:
        relpath = os.path.relpath(fullpath, config.content_folder)

    title = entry.get('title', '')

    values = {
        'file_path': fullpath,
        'category': entry.get('Category', utils.get_category(relpath)),
        'status': model.PublishStatus[entry.get('Status', 'SCHEDULED').upper()].value,
        'entry_type': entry.get('Entry-Type', ''),
        'slug_text': slugify.slugify(
            entry.get('Slug-Text',
                      markdown.render_title(title, markup=False, smartquotes=False))),
        'redirect_url': entry.get('Redirect-To', ''),
        'title': title,
        'sort_title': entry.get('Sort-Title', title),
        'canonical_path': entry.get('Path-Canonical', '')
    }

    entry_date = None
    if 'Date' in entry:
        try:
            entry_date = arrow.get(entry['Date'], tzinfo=config.timezone)
        except Exception as error:  # pylint:disable=broad-except
            LOGGER.info("Could not parse date %s (%s); setting to now", entry_date, error)
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
        except Exception as error:  # pylint:disable=broad-except
            LOGGER.info("Could not parse last-modified %s (%s); setting to now",
                        last_modified_str, error)
            last_modified = arrow.get()
            del entry['Last-Modified']
            entry['Last-Modified'] = last_modified.format()
            fixup_needed = True

    for ref_date in (entry_date, arrow.get(datetime.datetime.max)):
        try:
            values['display_date'] = ref_date.isoformat()
            values['utc_timestamp'] = ref_date.to('utc').int_timestamp
            values['local_date'] = ref_date.naive
            break
        except Exception as error:  # pylint:disable=broad-except
            LOGGER.warning("%s: Error setting entry date: %s", fullpath, error)

    LOGGER.debug("getting entry %s with id %d", fullpath, entry_id)

    remove_by_path(fullpath, entry_id)

    record = model.Entry.get(id=entry_id)
    if record:
        LOGGER.debug("Reusing existing entry %d", record.id)
        record.set(**values)
    else:
        record = model.Entry(id=entry_id, **values)

    # Update the entry ID
    if str(record.id) != entry['Entry-ID']:  # pylint:disable=no-member
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
            path_alias.set_alias(alias, model.AliasType.REDIRECT, entry=record)
        for alias in entry.get_all('Path-Mount', []):
            path_alias.set_alias(alias, model.AliasType.MOUNT, entry=record)
        for alias in entry.get_all('Path-Canonical', []):
            path_alias.set_alias(alias, model.AliasType.MOUNT, entry=record)

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
            utils.tag_key(t[0]): t
            for t in [(k, True) for k in entry.get_all('Hidden-Tag', [])]
            + [(k, False) for k in entry.get_all('Tag', [])]
        }
        remove_tags = []

        for etag in record.tags:
            LOGGER.debug("  has tag %s,%s", etag.tag.key, etag.tag.name)
            if etag.tag.key not in set_tags:
                remove_tags.append(etag)
        LOGGER.debug("set_tags %s remove_tags %s", set_tags, remove_tags)

        for etag in remove_tags:
            tag = etag.tag
            etag.delete()
            if len(tag.entries) == 0:
                LOGGER.debug("tag %s/%s entry count went to 0", tag.key, tag.name)
                tag.delete()

        for (key, tag) in set_tags.items():
            name, hidden = tag

            # get the underlying tag object
            tag_record = model.EntryTag.get(key=key)
            if not tag_record:
                LOGGER.debug("creating tag %s/%s", key, name)
                tag_record = model.EntryTag(key=key, name=name)
            elif name != tag_record.name and name != key and not hidden:
                LOGGER.debug("updating tag name %s/%s -> %s",
                             key, tag_record.name, name)
                tag_record.name = name

            # get the tag placement object
            etag = model.EntryTagged.get(tag=tag_record, entry=record)
            if not etag:
                etag = model.EntryTagged(tag=tag_record, entry=record, hidden=hidden)
            else:
                etag.hidden = hidden
            record.tags.add(etag)

        orm.commit()

    result = True

    # manage entry attachments
    with orm.db_session:
        from .category import search_path as cat_search_path
        search_path = (os.path.dirname(fullpath), cat_search_path(record.category))

        set_attach = set()
        for attach in entry.get_all('Attach', []):
            other = links.find_entry(attach, search_path)
            if other:
                set_attach.add(other)
            elif fixup_pass < 3:
                # The entry hasn't been found, so treat this as a fixup task
                # Pass 0 - this entry might not have an ID
                # Pass 1 - the other entry might not have an ID (since this can be scheduled
                #    before pass 1 of the other entry)
                # Pass 2 - everything should have an ID now
                LOGGER.info("Attempted to link to unknown entry '%s -> %s'; retrying",
                            relpath, attach)
                result = False
            else:
                LOGGER.warning(
                    "Failed to link to unknown entry '%s -> %s'; ignoring", relpath, attach)

        remove_attach = []
        for attach in record.attachments:
            if attach not in set_attach:
                remove_attach.append(attach)

        LOGGER.debug("set_attach %s remove_attach %s", set_attach, remove_attach)
        for attach in remove_attach:
            record.attachments.remove(attach)
        for attach in set_attach:
            record.attachments.add(attach)

        orm.commit()

    # do final fixups
    if record.status == model.PublishStatus.DRAFT.value:
        LOGGER.info("Not touching draft entry %s", fullpath)
    elif fixup_needed:
        LOGGER.info("Fixing up entry %s", fullpath)
        result = save_file(fullpath, entry, check_fingerprint)

    # register with the search index
    current_app.search_index.update(record, entry)

    return result


@orm.db_session
def expire_record(record):
    """ Expire a record for a missing entry """

    # This entry no longer exists so delete anything that relies on it
    orm.delete(pa for pa in model.PathAlias if pa.entry == record)

    # mark the entry as GONE to remove it from indexes
    record.status = model.PublishStatus.GONE.value
    orm.commit()


@orm.db_session
def remove_by_path(fullpath: str, entry_id: int):
    """ Remove entries for a path that don't match the expected ID """

    orm.delete(pa for pa in model.PathAlias  # type:ignore
               if pa.entry.file_path == fullpath
               and pa.entry.id != entry_id)
    orm.delete(e for e in model.Entry  # type:ignore
               if e.file_path == fullpath
               and e.id != entry_id)
    orm.commit()
