""" Full-text search stuff """
import os

import whoosh
import whoosh.fields
import whoosh.index
import whoosh.qparser
import whoosh.query
import whoosh.writing

from . import entry, model


class SearchIndex:
    """ Full-text search index for all entries """

    def __init__(self, config):
        self.schema = whoosh.fields.Schema(
            entry_id=whoosh.fields.ID(stored=True, unique=True),
            title=whoosh.fields.TEXT,
            content=whoosh.fields.TEXT,
            published=whoosh.fields.DATETIME,
            tags=whoosh.fields.KEYWORD(lowercase=True, commas=True),
            category=whoosh.fields.TEXT)

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
                tags=','.join(entry_file.get_all('tag') or []),
                category=record.category)

    def search(self, query: str):
        """ Searches with a text query """
        with self.index.searcher() as searcher:
            results = searcher.search(self.query_parser.parse("content", query))
            return [entry.Entry.load(model.Entry.get(id=int(hit['entry_id']))) for hit in results]
