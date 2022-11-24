# view.py
""" A view of entries """

import logging
import typing

import arrow
import flask
from werkzeug.utils import cached_property

from . import caching, queries, tokens, user, utils
from .entry import Entry

ViewSpec = typing.Dict[str, typing.Any]  # pylint:disable=invalid-name

LOGGER = logging.getLogger(__name__)

# Prioritization list for pagination
OFFSET_PRIORITY = ['date', 'start', 'last', 'first']

# Prioritization list for pagination type
#
# NOTE: date appears in here too so that if it appears as an offset it
# overrides the count
PAGINATION_PRIORITY = ['date', 'count']

# All spec keys that indicate a pagination
PAGINATION_SPECS = OFFSET_PRIORITY + PAGINATION_PRIORITY

SPAN_FORMATS = {
    'day': 'YYYY/MM/DD',
    'week': 'YYYY/MM/DD',
    'month': 'YYYY/MM',
    'year': 'YYYY/MM'
}


class View(caching.Memoizable):
    # pylint: disable=too-many-instance-attributes,too-many-public-methods
    """ A view of entries """

    __hash__ = caching.Memoizable.__hash__  # type:ignore

    @staticmethod
    @utils.stash
    def load(input_spec: ViewSpec):
        """ Generate a view.

        input_spec -- the parameters to the view. In addition to the values provided
        to queries.build_query, this also takes the following keys:
            count -- How many entries to include in a page
            order -- How to order the entries ('newest' or 'oldest')
        """
        return View(View.load.__name__, input_spec)

    def __init__(self, create_key, input_spec: ViewSpec):
        """ Instantiate the view """

        assert create_key == View.load.__name__, "View must be created with View.load()"

        # filter out any priority override things
        spec: ViewSpec = {
            k: v for k, v in input_spec.items()
            if k not in PAGINATION_SPECS
        }

        # pull in the first offset type that appears
        for offset in OFFSET_PRIORITY:
            if offset in input_spec:
                spec[offset] = input_spec[offset]
                break

        # pull in the first page type that appears
        paginated = False
        for pagination in PAGINATION_PRIORITY:
            if pagination in input_spec:
                paginated = True
                spec[pagination] = input_spec[pagination]
                break

        self._order_by = spec.get('order', 'newest')

        self.spec = spec

        if 'start' in spec and paginated:
            if self._order_by == 'oldest':
                self.spec['first'] = self.spec['start']
            elif self._order_by == 'newest':
                self.spec['last'] = self.spec['start']

        self._entries = queries.build_query(
            spec).order_by(*queries.ORDER_BY[self._order_by])

        if self.spec.get('date') is not None:
            _, self.type, _ = utils.parse_date(self.spec['date'])
        elif 'count' in self.spec:
            self.type = 'count'
        else:
            self.type = ''

    def _key(self):
        return repr(self.spec)

    def __str__(self):
        return str(self.link())

    @cached_property
    def first(self) -> typing.Optional[Entry]:
        """ Gets the first entry in the view """
        entries = self.entries()
        return entries[0] if entries else None

    @cached_property
    def last(self) -> typing.Optional[Entry]:
        """ Gets the last entry in the view """
        entries = self.entries()
        return entries[-1] if entries else None

    @cached_property
    def entries(self) -> typing.Callable[..., typing.List[Entry]]:
        """ Gets entries which are authorized for the current viewer """

        def _entries(unauthorized=0) -> typing.List[Entry]:
            count = self.spec.get('count')
            return Entry.filter_auth(self._entries, count, unauthorized)

        return utils.CallableProxy(_entries)

    @cached_property
    def unauthorized(self) -> typing.Callable[..., typing.List[Entry]]:
        """ Gets entries which the user is not allowed to view """

        def _unauthorized(count=None) -> typing.List[Entry]:
            result: typing.List[Entry] = []
            if count is None:
                count = self.spec.get('count')

            cur_user = user.get_active()
            for record in self._entries:
                if count is not None and len(result) >= count:
                    break

                if not record.is_authorized(cur_user):
                    tokens.request(cur_user)
                    result.append(Entry.load(record))

            return result

        return utils.CallableProxy(_unauthorized)

    @cached_property
    def has_unauthorized(self) -> bool:
        """ Returns whether there's entries that the user could see if they
        were authorized differently """

        count = self.spec.get('count')
        auth_count = 0
        cur_user = user.get_active()
        for record in self._entries:
            if count is not None and auth_count >= count:
                # we've already hit the end of the list
                break

            if not record.is_authorized(cur_user):
                # there's at least one unauthorized, so fast quit
                tokens.request(cur_user)
                return True

            auth_count += 1

        return False

    @cached_property
    def deleted(self) -> typing.List[Entry]:
        """ Gets the deleted entries from the view """
        query = queries.build_query({**self.spec,
                                     'future': False,
                                     '_deleted': True})
        if self.spec.get('count'):
            # We're using a count constraint, so we'll want to limit this to
            # entries that come before our next page of non-deleted results.
            #
            # We only use the next-page start because our pagination constraint
            # (if any) will have already limited this query appropriately, and
            # we consider deleted entries in the gap between two views to
            # belong to the first page of views.
            if self._order_by == 'oldest' and self.next:
                query = queries.where_before_entry(query, self.next.first)
            elif self._order_by == 'newest' and self.next:
                query = queries.where_after_entry(query, self.next.first)

        return [Entry.load(e) for e in query]

    @cached_property
    def count(self) -> int:
        """ Returns the number of entries in the view """
        return len(self.entries())

    @cached_property
    def last_modified(self) -> typing.Optional[Entry]:
        """ Gets the most recent modification time for all entries in the view """
        entries = self.entries()
        if entries:
            latest = max(entries, key=lambda x: x.last_modified)
            return arrow.get(latest.last_modified)
        return arrow.get()

    @cached_property
    def older(self) -> typing.Optional['View']:
        """ Gets the page of older items """
        older, _ = self._pagination
        return older

    @cached_property
    def newer(self) -> typing.Optional['View']:
        """ Gets the page of newer items """
        _, newer = self._pagination
        return newer

    @cached_property
    def previous(self) -> typing.Optional['View']:
        """ Gets the previous page, respecting sort order """
        if self._order_by == 'oldest':
            return self.older
        if self._order_by == 'newest':
            return self.newer
        return None

    @cached_property
    def next(self) -> typing.Optional['View']:
        """ Gets the next page, respecting sort order """
        if self._order_by == 'oldest':
            return self.newer
        if self._order_by == 'newest':
            return self.older
        return None

    @cached_property
    def newest(self) -> typing.Optional[Entry]:
        """ Gets the newest entry in the view, regardless of sort order """
        if self._order_by == 'newest':
            return self.first
        if self._order_by == 'oldest':
            return self.last
        return max(self.entries(), key=lambda x: (x.date, x.id))

    @cached_property
    def oldest(self) -> typing.Optional[Entry]:
        """ Gets the oldest entry in the view, regardless of sort order """
        if self._order_by == 'newest':
            return self.last
        if self._order_by == 'oldest':
            return self.first
        return min(self.entries(), key=lambda x: (x.date, -x.id))

    @cached_property
    def paging(self) -> str:
        """ Gets the pagination type; compatible with entry.archive(page_type=...) """
        if 'date' in self.spec:
            _, date_span, _ = utils.parse_date(self.spec['date'])
            return date_span
        return 'offset'

    @cached_property
    def pages(self) -> typing.List['View']:
        """ Gets a list of all pages for this view """
        pages = []

        cur: typing.Optional[View] = self.previous
        while cur is not None:
            pages.append(cur)
            cur = cur.previous
        pages.reverse()

        cur = self
        while cur is not None:
            pages.append(cur)
            cur = cur.next

        return pages

    @cached_property
    def range(self) -> typing.Callable[..., str]:
        """ Gets a localizable string describing the view range """
        def _view_name(**formats) -> str:
            if not any(k for k in PAGINATION_SPECS if k in self.spec):
                # We don't have anything that specifies a pagination constraint, so
                # we don't have a name
                return ''

            if not self.oldest or not self.newest:
                # We don't have any entries, so we don't have a name
                return ''

            if 'date' in self.spec:
                _, span_type, span_format = utils.parse_date(self.spec['date'])
            elif self.oldest.date.year != self.newest.date.year:
                span_type = 'year'
                span_format = utils.YEAR_FORMAT
            elif self.oldest.date.month != self.newest.date.month:
                span_type = 'month'
                span_format = utils.MONTH_FORMAT
            else:
                span_type = 'day'
                span_format = utils.DAY_FORMAT

            date_format = formats.get(
                span_type, SPAN_FORMATS.get(span_type, span_format))

            oldest = self.oldest.date.format(date_format)
            if self.oldest == self.newest:
                return oldest

            newest = self.newest.date.format(date_format)

            if oldest == newest:
                template = formats.get('single', '{oldest} ({count})')
            else:
                template = formats.get(
                    'span', '{oldest} — {newest} ({count})')

            return template.format(count=len(self.entries()),
                                   oldest=oldest,
                                   newest=newest)
        return utils.CallableProxy(_view_name)

    @cached_property
    def link(self) -> typing.Callable[..., str]:
        """ Gets a link back to this view """

        def _link(template='', absolute=False, category=None, **kwargs) -> str:
            args = {}
            if 'date' in self.spec:
                args['date'] = self.spec['date']
            else:
                for k in OFFSET_PRIORITY:
                    if k in self.spec:
                        val = self.spec[k]
                        if isinstance(val, (str, int)):
                            args['id'] = val
                        elif hasattr(val, 'start'):
                            # the item was an object, so we want the object's
                            # id
                            args['id'] = val.id
                        else:
                            raise ValueError(f"key {k} is of type {type(val)}")
                        break

            taglist = kwargs.get('tag', self.spec.get('tag'))
            if taglist:
                args['tag'] = list(utils.TagSet(utils.as_list(taglist)).keys())

            return flask.url_for('category',
                                 **args,
                                 template=template,
                                 category=category if category else self.spec.get(
                                     'category'),
                                 _external=absolute,
                                 **kwargs)

        return utils.CallableProxy(_link)

    @cached_property
    def tags(self) -> utils.TagSet:
        """ Returns a list of all the tags applied to this view """
        tag_list = self.spec.get('tag', [])
        return utils.TagSet(utils.as_list(tag_list))

    @cached_property
    def current(self) -> typing.Callable[..., 'View']:
        """ Gets a version of this view without any pagination offsets """

        def _get_current(**restrict) -> 'View':
            spec = {k: v for (k, v) in self.spec.items()
                    if k not in OFFSET_PRIORITY}
            return View.load({**spec, **restrict})

        return utils.CallableProxy(_get_current)

    @cached_property
    def is_current(self) -> bool:
        """ Returns true if this is equivalent to self.current """
        for k in self.spec.keys():
            if k in OFFSET_PRIORITY:
                return False
        return True

    @cached_property
    def _pagination(self) -> typing.Tuple[typing.Optional['View'], typing.Optional['View']]:
        """ Compute the neighboring pages from this view.

        Returns a tuple of older page, newer page.
        """

        base = {key: val for key, val in self.spec.items()
                if key not in OFFSET_PRIORITY}

        if 'date' in self.spec:
            LOGGER.debug('by date')
            return self._get_date_pagination(base)

        if 'count' in self.spec:
            LOGGER.debug('by count')
            return self._get_count_pagination(base)

        # we're not paginating
        return None, None

    def _get_date_pagination(self,
                             base: ViewSpec
                             ) -> typing.Tuple[typing.Optional['View'], typing.Optional['View']]:
        """ Compute the pagination for date-based views """
        date, interval, date_format = utils.parse_date(self.spec['date'])
        start_date, end_date = date.span(interval)

        base_query = queries.build_query(base)
        oldest_neighbor = base_query.filter(lambda e: e.local_date < start_date.datetime)\
            .order_by(*queries.ORDER_BY['newest']).first()
        newest_neighbor = base_query.filter(lambda e: e.local_date > end_date.datetime)\
            .order_by(*queries.ORDER_BY['oldest']).first()

        older_view: typing.Optional['View'] = None
        newer_view: typing.Optional['View'] = None

        if newest_neighbor:
            newer_date = newest_neighbor.display_date
            newer_view = View.load({**base,
                                    'order': self._order_by,
                                    'date': arrow.get(newer_date).format(date_format)})

        if oldest_neighbor:
            older_date = oldest_neighbor.display_date
            older_view = View.load({**base,
                                    'order': self._order_by,
                                    'date': arrow.get(older_date).format(date_format)})

        return older_view, newer_view

    def _get_count_pagination(self,
                              base: ViewSpec
                              ) -> typing.Tuple[typing.Optional['View'], typing.Optional['View']]:
        """ Compute the pagination for count-based views """

        oldest = self.oldest
        newest = self.newest

        oldest_neighbor = View.load({
            **base,
            'before': oldest,
            'order': 'newest'
        }).first if oldest else None

        newest_neighbor = View.load({
            **base,
            'after': newest,
            'order': 'oldest'
        }).first if newest else None

        count = self.spec['count']

        out_spec = {**base, 'count': count, 'order': self._order_by}

        if self._order_by == 'newest':
            older_view = View.load({**out_spec,
                                    'last': oldest_neighbor}) if oldest_neighbor else None

            newer_count = View.load({**base,
                                     'first': newest_neighbor,
                                     'order': 'oldest',
                                     'count': count}) if newest_neighbor else None
            newer_view = View.load({**out_spec,
                                    'last': newer_count.last}) if newer_count else None

            return older_view, newer_view

        if self._order_by == 'oldest':
            older_count = View.load({**base,
                                     'last': oldest_neighbor,
                                     'order': 'newest',
                                     'count': count}) if oldest_neighbor else None
            older_view = View.load({**out_spec,
                                    'first': older_count.last}) if older_count else None

            newer_view = View.load({**out_spec,
                                    'first': newest_neighbor}) if newest_neighbor else None

            return older_view, newer_view

        return None, None

    def __call__(self, **restrict):
        return View.load({**self.spec, **restrict})

    def __iter__(self):
        return self.entries().__iter__()

    def tag_add(self, *tags: utils.ListLike[str]) -> 'View':
        """ Return a view with the specified tags added """
        return View.load({**self.spec, 'tag': self.tags | set(tags)})

    def tag_remove(self, *tags: utils.ListLike[str]) -> 'View':
        """ Return a view with the specified tags removed """
        return View.load({**self.spec, 'tag': self.tags - set(tags)})

    def tag_toggle(self, *tags: utils.ListLike[str]) -> 'View':
        """ Return a view with the specified tags toggled """
        return View.load({**self.spec, 'tag': self.tags ^ set(tags)})


def get_view(**kwargs) -> View:
    """ Wrapper function for constructing a view from scratch """
    return View.load(input_spec=kwargs)


def parse_view_spec(args) -> ViewSpec:
    """ Parse a view specification from a request arg list """

    view_spec = {}

    if 'date' in args:
        view_spec['date'] = args['date']
    elif 'id' in args:
        view_spec['start'] = args['id']

    if 'tag' in args:
        view_spec['tag'] = args.getlist('tag')
        if len(view_spec['tag']) == 1:
            view_spec['tag'] = args['tag']

    return view_spec
