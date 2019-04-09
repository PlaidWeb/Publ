# view.py
""" A view of entries """

import arrow
import flask
from werkzeug.utils import cached_property
from pony import orm

from . import model, utils, queries
from .entry import Entry

# Prioritization list for pagination
OFFSET_PRIORITY = ['date', 'start', 'last', 'first']

# Prioritization list for pagination type
#
# NOTE: date appears in here too so that if it appears as an offset it
# overrides the count
PAGINATION_PRIORITY = ['date', 'count']

# All spec keys that indicate a pagination
PAGINATION_SPECS = OFFSET_PRIORITY + PAGINATION_PRIORITY

#: Ordering queries for different sort orders
ORDER_BY = {
    'newest': (orm.desc(model.Entry.local_date), orm.desc(model.Entry.id)),
    'oldest': (model.Entry.local_date, model.Entry.id),
    'title': (model.Entry.sort_title, model.Entry.id)
}

REVERSE_ORDER_BY = {
    'newest': (model.Entry.local_date, model.Entry.id),
    'oldest': (orm.desc(model.Entry.local_date), orm.desc(model.Entry.id)),
    'title': (orm.desc(model.Entry.sort_title), orm.desc(model.Entry.id))
}


SPAN_FORMATS = {
    'day': 'YYYY/MM/DD',
    'week': 'YYYY/MM/DD',
    'month': 'YYYY/MM',
    'year': 'YYYY/MM'
}


class View:
    # pylint: disable=too-many-instance-attributes,too-few-public-methods
    """ A view of entries """

    def __init__(self, input_spec=None):
        """ Generate a view.

        input_spec -- the parameters to the view. In addition to the values provided
        to queries.build_query, this also takes the following keys:
            count -- How many entries to include in a page
            order -- How to order the entries ('newest' or 'oldest')
        """

        # filter out any priority override things
        spec = {
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

        self._query = queries.build_query(
            spec).order_by(*ORDER_BY[self._order_by])

        if 'count' in spec:
            self._entries = self._query[:spec['count']]
        else:
            self._entries = self._query[:]

        if self.spec.get('date') is not None:
            _, self.type, _ = utils.parse_date(self.spec['date'])
        elif 'count' in self.spec:
            self.type = 'count'
        else:
            self.type = None

    def __repr__(self):
        return repr(self.spec)

    def __str__(self):
        return str(self._link())

    def _link(self, template='', absolute=False, category=None, **kwargs):
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
                        # the item was an object, so we want the object's id
                        args['id'] = val.id
                    else:
                        raise ValueError(
                            "key {} is of type {}".format(k, type(val)))
                    break

        if 'tag' in self.spec:
            args['tag'] = self.spec['tag']

        return flask.url_for('category',
                             **args,
                             template=template,
                             category=category if category else self.spec.get(
                                 'category'),
                             _external=absolute,
                             **kwargs)

    @cached_property
    def first(self):
        """ Gets the first entry in the view """
        return self.entries[0] if self.entries else None

    @cached_property
    def last(self):
        """ Gets the last entry in the view """
        return self.entries[-1] if self.entries else None

    @cached_property
    def entries(self):
        """ Gets the entries for the view """
        return [Entry(e) for e in self._entries]

    @cached_property
    def deleted(self):
        """ Gets the deleted entries from the view """
        query = queries.build_query({**self.spec,
                                     'future': False,
                                     '_deleted': True})
        return [Entry(e) for e in query]

    @cached_property
    def count(self):
        """ Returns the number of entries in the view """
        return len(self.entries)

    @cached_property
    def last_modified(self):
        """ Gets the most recent modification time for all entries in the view """
        if self.entries:
            latest = max(self.entries, key=lambda x: x.last_modified)
            return arrow.get(latest.last_modified)
        return arrow.get()

    @cached_property
    def older(self):
        """ Gets the page of older items """
        older, _ = self._pagination
        return older

    @cached_property
    def newer(self):
        """ Gets the page of newer items """
        _, newer = self._pagination
        return newer

    @cached_property
    def previous(self):
        """ Gets the previous page, respecting sort order """
        if self._order_by == 'oldest':
            return self.older
        if self._order_by == 'newest':
            return self.newer
        return None

    @cached_property
    def next(self):
        """ Gets the next page, respecting sort order """
        if self._order_by == 'oldest':
            return self.newer
        if self._order_by == 'newest':
            return self.older
        return None

    @cached_property
    def newest(self):
        """ Gets the newest entry in the view, regardless of sort order """
        if self._order_by == 'newest':
            return self.first
        if self._order_by == 'oldest':
            return self.last
        return max(self.entries, key=lambda x: (x.date, x.id))

    @cached_property
    def oldest(self):
        """ Gets the oldest entry in the view, regardless of sort order """
        if self._order_by == 'newest':
            return self.last
        if self._order_by == 'oldest':
            return self.first
        return min(self.entries, key=lambda x: (x.date, -x.id))

    @cached_property
    def paging(self):
        """ Gets the pagination type; compatible with entry.archive(page_type=...) """
        if 'date' in self.spec:
            _, date_span, _ = utils.parse_date(self.spec['date'])
            return date_span
        return 'offset'

    @cached_property
    def pages(self):
        """ Gets a list of all pages for this view """
        cur = self
        pages = []
        while cur.previous:
            cur = cur.previous
        while cur:
            pages.append(cur)
            cur = cur.next
        return pages

    @cached_property
    def range(self):
        """ Gets a localizable string describing the view range """
        return utils.CallableProxy(self._view_name)

    @cached_property
    def link(self):
        """ Gets a link back to this view """
        return utils.CallableProxy(self._link)

    @cached_property
    def tags(self):
        """ Returns a list of all the tags applied to this view """
        tag_list = self.spec.get('tag', [])
        if isinstance(tag_list, (list, set, tuple)):
            return list(tag_list)
        return [tag_list]

    @cached_property
    def _pagination(self):
        """ Compute the neighboring pages from this view.

        Returns a tuple of older page, newer page.
        """

        oldest = self.oldest
        newest = self.newest

        base = {key: val for key, val in self.spec.items()
                if key not in OFFSET_PRIORITY}

        oldest_neighbor = View({
            **base,
            'before': oldest,
            'order': 'newest'
        }).first if oldest else None

        newest_neighbor = View({
            **base,
            'after': newest,
            'order': 'oldest'
        }).first if newest else None

        if 'date' in self.spec:
            return self._get_date_pagination(base, oldest_neighbor, newest_neighbor)

        if 'count' in self.spec:
            return self._get_count_pagination(base, oldest_neighbor, newest_neighbor)

        # we're not paginating
        return None, None

    def _get_date_pagination(self, base, oldest_neighbor, newest_neighbor):
        """ Compute the pagination for date-based views """
        _, span, date_format = utils.parse_date(self.spec['date'])

        if newest_neighbor:
            newer_date = newest_neighbor.date.span(span)[0]
            newer_view = View({**base,
                               'order': self._order_by,
                               'date': newer_date.format(date_format)})
        else:
            newer_view = None

        if oldest_neighbor:
            older_date = oldest_neighbor.date.span(span)[0]
            older_view = View({**base,
                               'order': self._order_by,
                               'date': older_date.format(date_format)})
        else:
            older_view = None

        return older_view, newer_view

    def _get_count_pagination(self, base, oldest_neighbor, newest_neighbor):
        """ Compute the pagination for count-based views """

        count = self.spec['count']

        out_spec = {**base, 'count': count, 'order': self._order_by}

        if self._order_by == 'newest':
            older_view = View({**out_spec,
                               'last': oldest_neighbor}) if oldest_neighbor else None

            newer_count = View({**base,
                                'first': newest_neighbor,
                                'order': 'oldest',
                                'count': count}) if newest_neighbor else None
            newer_view = View({**out_spec,
                               'last': newer_count.last}) if newer_count else None

            return older_view, newer_view

        if self._order_by == 'oldest':
            older_count = View({**base,
                                'last': oldest_neighbor,
                                'order': 'newest',
                                'count': count}) if oldest_neighbor else None
            older_view = View({**out_spec,
                               'first': older_count.last}) if older_count else None

            newer_view = View({**out_spec,
                               'first': newest_neighbor}) if newest_neighbor else None

            return older_view, newer_view

        return None, None

    def __call__(self, **restrict):
        return View({**self.spec, **restrict})

    def tag_add(self, *tags):
        """ Return a view with the specified tags added """
        return View({**self.spec, 'tag': list(set(self.tags) | set(tags))})

    def tag_remove(self, *tags):
        """ Return a view with the specified tags removed """
        return View({**self.spec, 'tag': list(set(self.tags) - set(tags))})

    def tag_toggle(self, *tags):
        """ Return a view with the specified tags toggled """
        return View({**self.spec, 'tag': list(set(self.tags) ^ set(tags))})

    def _view_name(self, **formats):
        if not any(k for k in PAGINATION_SPECS if k in self.spec):
            # We don't have anything that specifies a pagination constraint, so
            # we don't have a name
            return None

        if not self.oldest or not self.newest:
            # We don't have any entries, so we don't have a name
            return None

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
        if len(self.entries) == 1:
            return oldest

        newest = self.newest.date.format(date_format)

        if oldest == newest:
            template = formats.get('single', '{oldest} ({count})')
        else:
            template = formats.get(
                'span', '{oldest} — {newest} ({count})')

        return template.format(count=len(self.entries),
                               oldest=oldest,
                               newest=newest)


def get_view(**kwargs):
    """ Wrapper function for constructing a view from scratch """
    return View(input_spec=kwargs)


def parse_view_spec(args):
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
