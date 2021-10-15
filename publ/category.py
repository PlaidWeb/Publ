# category.py
""" The Category object passed to entry and category views """

import collections
import email
import logging
import os
import typing

import flask
from flask import url_for
from pony import orm
from werkzeug.utils import cached_property

from . import entry  # pylint: disable=cyclic-import
from . import caching, markdown, model, path_alias, queries, utils
from .config import config

LOGGER = logging.getLogger(__name__)

TagCount = collections.namedtuple('TagCount', ['name', 'count'])


def load_metafile(filepath):
    """ Load a metadata file from the filesystem """
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            return email.message_from_file(file)
    except FileNotFoundError:
        LOGGER.warning("Category file %s not found", filepath)

        # SQLite doesn't support cascading deletes, so clean up
        orm.delete(pa for pa in model.PathAlias if pa.category.file_path == filepath)

        orm.delete(c for c in model.Category if c.file_path == filepath)
        orm.commit()

    return None


def search_path(category: str) -> str:
    """ Return the file search path for a named category """
    return os.path.join(config.content_folder, category)


class Category(caching.Memoizable):
    """ Wrapper for category information """
    # pylint: disable=too-few-public-methods,too-many-instance-attributes

    __hash__ = caching.Memoizable.__hash__  # type:ignore

    @staticmethod
    @utils.stash
    def load(path: str):
        """ Get a category wrapper object

        path -- the path to the category
        """
        return Category(Category.load.__name__, path)

    def __init__(self, create_key, path: str):
        """ Initialize a category wrapper """

        assert create_key == Category.load.__name__, "Category must be created with Category.load()"

        if path is None:
            path = ''

        self.path = path
        self.basename = os.path.basename(path)

        subcat_query = orm.select(e.category for e in model.Entry if e.visible)  # type:ignore
        if path:
            subcat_query = orm.select(
                c for c in subcat_query if c.startswith(path + '/'))
        else:
            subcat_query = orm.select(c for c in subcat_query if c != '')
        self._subcats_recursive = subcat_query

        self._record = model.Category.get(category=path)

    def _key(self):
        return self.path

    @cached_property
    def link(self) -> typing.Callable[..., str]:
        """ Returns a link to the category.

        Takes optional view arguments, as well as the following optional arguments:

        template -- which template to generate the link against

        """
        def _link(template='', absolute=False, **kwargs) -> str:
            return url_for('category',
                           category=self.path,
                           template=template,
                           _external=absolute,
                           **kwargs)

        return utils.CallableProxy(_link)

    @cached_property
    def subcats(self) -> typing.Callable[..., str]:
        """ Returns a list of subcategories.

        Takes the following arguments:

        recurse -- whether to include their subcategories as well (default: False)

        """
        def _get_subcats(recurse=False) -> typing.List["Category"]:
            """ Get the subcategories of this category

            recurse -- whether to include their subcategories as well
            """

            if recurse:
                # No need to filter
                return sorted([Category.load(e) for e in self._subcats_recursive],
                              key=lambda cat: tuple(crumb.sort_name for crumb in cat.breadcrumb))

            # get all the subcategories, with only the first subdir added

            # number of path components to ingest
            parts = len(self.path.split('/')) + 1 if self.path else 1

            # convert the subcategories into separated pathlists with only 'parts'
            # parts, then rejoin back into a path and make unique
            subcats = {'/'.join(c.split('/', parts)[:parts]) for c in self._subcats_recursive}

            # convert to a bunch of Category objects
            return sorted([Category.load(c) for c in subcats], key=lambda c: c.sort_name)

        return utils.CallableProxy(_get_subcats)

    @cached_property
    def first(self) -> typing.Callable[..., typing.Optional[entry.Entry]]:
        """ Returns the first entry in the category.

        Takes optional view arguments.
        """
        def _first(**spec) -> typing.Optional[entry.Entry]:
            """ Get the earliest entry in this category, optionally including subcategories """
            for record in self._entries(spec).order_by(model.Entry.local_date,
                                                       model.Entry.id)[:1]:
                return entry.Entry.load(record)
            return None

        return utils.CallableProxy(_first)

    @cached_property
    def last(self) -> typing.Callable[..., typing.Optional[entry.Entry]]:
        """ Returns the last entry in the category.

        Takes optional view arguments.
        """
        def _last(**spec) -> typing.Optional[entry.Entry]:
            """ Get the latest entry in this category, optionally including subcategories """
            for record in self._entries(spec).order_by(orm.desc(model.Entry.local_date),
                                                       orm.desc(model.Entry.id))[:1]:
                return entry.Entry.load(record)
            return None

        return utils.CallableProxy(_last)

    @cached_property
    def _meta(self) -> typing.Optional[email.message.Message]:
        if self._record and self._record.file_path:
            return load_metafile(self._record.file_path)

        return None

    @cached_property
    def name(self) -> typing.Callable[..., str]:
        """ Get the display name of the category. Accepts the following arguments:

        markup -- If True, convert it from Markdown to HTML; otherwise, strip
            all markup (default: True)
        no_smartquotes -- if True, preserve quotes and other characters as originally
            presented
        markdown_extensions -- a list of markdown extensions to use
        """
        if self._meta and self._meta.get('name'):
            # get it from the meta file
            name = self._meta.get('name')
        else:
            # infer it from the basename
            name = self.basename.replace('_', ' ').title()

        def _name(markup=True, no_smartquotes=False, markdown_extensions=None) -> str:
            return markdown.render_title(name, markup, no_smartquotes,
                                         markdown_extensions)
        return utils.CallableProxy(_name)

    @cached_property
    def description(self) -> typing.Callable[..., str]:
        """ Get the textual description of the category """
        def _description(**kwargs) -> str:
            if self._meta:
                return flask.Markup(markdown.to_html(self._meta.get_payload(),
                                                     args=kwargs,
                                                     search_path=self.search_path,
                                                     counter=markdown.ItemCounter()))
            return ''

        if self._meta and self._meta.get_payload():
            return utils.TrueCallableProxy(_description)
        return utils.CallableValue('')

    @cached_property
    def search_path(self) -> str:
        """ Get the file search path for this category """
        return search_path(self.path)

    @cached_property
    def breadcrumb(self) -> typing.List["Category"]:
        """ Get the category hierarchy leading up to this category, including
        root and self.

        For example, path/to/long/category will return a list containing
        Category.load('path'), Category.load('path/to'), and Category.load('path/to/long').
        """
        ret = []
        here: typing.Optional[Category] = self
        while here:
            ret.append(here)
            here = here.parent
        return list(reversed(ret))

    @cached_property
    def sort_name(self) -> str:
        """ Get the sorting name of this category """
        if self._record and self._record.sort_name:
            return self._record.sort_name
        return self.name(markup=False)

    @cached_property
    def tags(self) -> typing.Callable[..., typing.List[TagCount]]:
        """ Get the list of tags associated with this category's entries.

        Takes optional view arguments (including recurse)

        Returns a list of category.TagCount tuples like `(tag='foo', count=5)`
        """
        def _tags(**spec) -> typing.List[TagCount]:
            entries = self._entries(spec)
            etags = orm.select((tag.tag, orm.count(tag.tag, distinct=False))
                               for e in entries for tag in e.tags if not tag.hidden)
            return [TagCount(tag.name, count) for (tag, count) in etags]
        return utils.CallableProxy(_tags)

    def __getattr__(self, name):
        """ Proxy undefined properties to the meta file """
        if self._meta:
            return self._meta.get(name)
        return None

    def get(self, name):
        """ Get a single metadata value """
        if self._meta:
            return self._meta.get(name)
        return None

    def get_all(self, name):
        """ Get all matching metadata values """
        if self._meta:
            return self._meta.get_all(name) or []
        return None

    def __str__(self):
        return self.path

    def __eq__(self, other):
        return str(other) == str(self)

    def __lt__(self, other):
        return self.path < other.path

    @cached_property
    def parent(self) -> typing.Optional["Category"]:
        """ Get the parent category """
        if self.path:
            return Category.load(os.path.dirname(self.path))
        return None

    @cached_property
    def root(self):
        """ Get the root category object. Equivalent to `breadcrumb[0]` but faster/easier. """
        if self.path:
            return Category.load(None)
        return self

    def _entries(self, spec):
        """ Return a model query to get our entry records """
        return queries.build_query({**spec, 'category': self})


@orm.db_session(retry=5)
def scan_file(fullpath, relpath) -> bool:
    """ scan a file and put it into the index """

    meta = load_metafile(fullpath)
    if not meta:
        return True

    # update the category meta file mapping
    category = meta.get('Category', utils.get_category(relpath))
    values = {
        'category': category,
        'file_path': fullpath,
        'sort_name': meta.get('Sort-Name', '')
    }

    LOGGER.debug("setting category %s to metafile %s", category, fullpath)
    record = model.Category.get(category=category)
    if record:
        record.set(**values)
    else:
        record = model.Category(**values)

    # update other relationships to the index
    path_alias.remove_aliases(record)
    for alias in meta.get_all('Path-Alias', []):
        path_alias.set_alias(alias, model.AliasType.REDIRECT, category=record)
    for alias in meta.get_all('Path-Mount', []):
        path_alias.set_alias(alias, model.AliasType.MOUNT, category=record)

    orm.commit()

    return True
