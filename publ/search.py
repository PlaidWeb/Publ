""" Full-text search stuff """
import logging
import os

import whoosh
import whoosh.fields
import whoosh.index
import whoosh.qparser
import whoosh.query
import whoosh.writing

from . import entry, model

LOGGER = logging.getLogger(__name__)


class SearchIndex:
    """ Full-text search index for all entries """

    def __init__(self, config):
        self.schema = whoosh.fields.Schema(
            entry_id=whoosh.fields.ID(stored=True, unique=True),
            title=whoosh.fields.TEXT,
            content=whoosh.fields.TEXT,
            published=whoosh.fields.DATETIME,
            tag=whoosh.fields.KEYWORD(lowercase=True, commas=True),
            category=whoosh.fields.ID)

        if not os.path.exists(config.search_index):
            os.mkdir(config.search_index)

        if not whoosh.index.exists_in(config.search_index):
            self.index = whoosh.index.create_in(config.search_index, self.schema)
        else:
            self.index = whoosh.index.open_dir(config.search_index)

        self.query_parser = whoosh.qparser.QueryParser("content", self.index.schema)

    def update(self, record, entry_file):
        """ Add an entry to the content index """

        with whoosh.writing.AsyncWriter(self.index) as writer:
            writer.update_document(
                entry_id=str(record.id),
                title=record.title,
                content=entry_file.get_payload(),
                published=record.utc_date,
                tag=','.join(entry_file.get_all('tag') or []),
                category=record.category)

    def query(self, query: str, category=None, recurse=False):
        """ Searches with a text query """
        LOGGER.debug('query: %s  category: %s  recurse: %s', query, category, recurse)
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

            LOGGER.debug('parse result: %s', parsed)
            results = searcher.search(parsed)
            return [entry.Entry.load(model.Entry.get(id=int(hit['entry_id'])))
                    for hit in results]
