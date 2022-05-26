""" Full-text search stuff """
import datetime
import email
import logging
import os
import typing

try:
    import whoosh
    import whoosh.fields
    import whoosh.index
    import whoosh.qparser
    import whoosh.query
    import whoosh.writing
except ImportError:
    whoosh = None

from pony import orm
from werkzeug.utils import cached_property

from . import model, tokens, user, utils
from .entry import Entry

LOGGER = logging.getLogger(__name__)
SCHEMA_VERSION = 2


class SearchResults:
    """ Result set from a full-text search """

    def __init__(self, results):
        self._entries = [record
                         for record in [model.Entry.get(id=int(hit['entry_id']))
                                        for hit in results]
                         if record and record.visible]

    @cached_property
    def has_unauthorized(self):
        """ Returns whether there are any unauthorized entries present """

        cur_user = user.get_active()

        for record in self._entries:
            if not record.is_authorized(cur_user):
                tokens.request(cur_user)
                return True
        return False

    @cached_property
    def entries(self) -> typing.Callable[..., typing.List[Entry]]:
        """ Returns the entries in the search results """
        def _entries(unauthorized=0) -> typing.List[Entry]:
            return Entry.filter_auth(self._entries, unauthorized=unauthorized)

        return utils.CallableProxy(_entries)

    def __iter__(self):
        return self.entries().__iter__()

    def __len__(self):
        return len(self._entries)

    def __bool__(self):
        return bool(self._entries)


class SearchIndex:
    """ Full-text search index for all entries """

    def __init__(self, config):
        if not config.search_index:
            self.index = None
            return

        if not whoosh:
            self.index = None
            LOGGER.error(
                "Search index configured but required libraries are not installed. "
                "See https://publ.plaidweb.site/manual/865-Python-API#search_index")

        self.schema = whoosh.fields.Schema(
            entry_id=whoosh.fields.ID(stored=True, unique=True),
            title=whoosh.fields.TEXT,
            content=whoosh.fields.TEXT,
            published=whoosh.fields.DATETIME,
            tag=whoosh.fields.KEYWORD(lowercase=True, commas=True),
            category=whoosh.fields.ID,
            status=whoosh.fields.NUMERIC)

        if not os.path.exists(config.search_index):
            os.mkdir(config.search_index)

        with orm.db_session:
            version = model.GlobalConfig.get(key='search_index_version')

            if (not whoosh.index.exists_in(config.search_index)
                or not version
                    or version.int_value != SCHEMA_VERSION):
                # either the index doesn't exist or it's got the wrong schema;
                # (re)create it
                self.index = whoosh.index.create_in(config.search_index, self.schema)
                if version:
                    version.int_value = SCHEMA_VERSION
                else:
                    version = model.GlobalConfig(key='search_index_version',
                                                 int_value=SCHEMA_VERSION)
            else:
                self.index = whoosh.index.open_dir(config.search_index)

        self.query_parser = whoosh.qparser.QueryParser("content", self.index.schema)

    def update(self, record: model.Entry, entry_file: email.message.EmailMessage):
        """
        Add an entry to the content index
        """

        if not self.index:
            return

        if record.status not in (model.PublishStatus.PUBLISHED.value,
                                 model.PublishStatus.SCHEDULED.value):
            self.index.delete_by_term("entry_id", str(record.id))
            return

        with whoosh.writing.AsyncWriter(self.index) as writer:
            writer.update_document(
                entry_id=str(record.id),
                title=record.title,
                content=entry_file.get_payload(),
                published=datetime.datetime.fromtimestamp(record.utc_timestamp),
                tag=','.join(entry_file.get_all('tag') or []),
                category=record.category,
                status=record.status)

    def query(self, query: str,
              category=None, recurse=False,
              count=None, page=None,
              future=False):
        """
        Searches with a text query

        :param category: The category to search on; None to avoid restriction
        :param bool recurse: Whether to also match subcategories
        :param int count: The number of entries per page
        :param int page: The page number to retrieve
        :param bool future: Whether to retrieve entries that aren't yet visible
        """
        # pylint:disable=too-many-arguments
        LOGGER.debug('query: %s  category: %s  recurse: %s  future: %s',
                     query, category, recurse, future)

        if not self.index:
            return SearchResults([])

        with self.index.searcher() as searcher:
            parsed = self.query_parser.parse(query)

            if category is not None:
                if str(category):
                    # We're in a category other than root
                    cat_term = whoosh.query.Term("category", str(category))
                    if recurse:
                        cat_term = whoosh.query.Or([cat_term,
                                                    whoosh.query.Prefix("category",
                                                                        f"{str(category)}/")])
                    parsed = whoosh.query.And([parsed, cat_term])
                elif not recurse:
                    # We're in root and not recursing, so we need to match empty
                    parsed = whoosh.query.And([parsed, whoosh.query.Term("category", "")])

            if not future:
                parsed = whoosh.query.And([
                    parsed,
                    whoosh.query.Or([
                        whoosh.query.Term("status", model.PublishStatus.PUBLISHED.value),
                        whoosh.query.DateRange("published", None, datetime.datetime.now()),
                    ])
                ])

            LOGGER.debug('parse result: %s', parsed)
            if page is not None:
                results = searcher.search_page(parsed, page, pagelen=count)
            else:
                results = searcher.search(parsed, limit=count)

            return SearchResults(results)
