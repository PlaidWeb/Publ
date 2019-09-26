# category.py
""" The Category object passed to entry and category views """

import collections
import email
import functools
import logging
import os

import flask
from flask import url_for
from pony import orm
from werkzeug.utils import cached_property

from . import entry  # pylint: disable=cyclic-import
from . import caching, config, markdown, model, path_alias, queries, utils

LOGGER = logging.getLogger(__name__)

TagCount = collections.namedtuple('TagCount', ['name', 'count'])


@functools.lru_cache(10)
def load_metafile(filepath):
    """ Load a metadata file from the filesystem """
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            return email.message_from_file(file)
    except FileNotFoundError:
        LOGGER.warning("Category file %s not found", filepath)
        orm.delete(c for c in model.Category if c.file_path == filepath)
        orm.commit()

    return None


class Category(caching.Memoizable):
    """ Wrapper for category information """
    # pylint: disable=too-few-public-methods,too-many-instance-attributes

    def __init__(self, path):
        """ Initialize a category wrapper

        path -- the path to the category
        """

        if path is None:
            path = ''

        self.path = path
        self.basename = os.path.basename(path)

        subcat_query = orm.select(e.category for e in model.Entry)
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
    def link(self):
        """ Returns a link to the category.

        Takes optional view arguments, as well as the following optional arguments:

        template -- which template to generate the link against

        """
        def _link(template='', absolute=False, **kwargs):
            return url_for('category',
                           category=self.path,
                           template=template,
                           _external=absolute,
                           **kwargs)

        return utils.CallableProxy(_link)

    @cached_property
    def subcats(self):
        """ Returns a list of subcategories.

        Takes the following arguments:

        recurse -- whether to include their subcategories as well (default: False)

        """
        def _get_subcats(recurse=False):
            """ Get the subcategories of this category

            recurse -- whether to include their subcategories as well
            """

            if recurse:
                # No need to filter
                return sorted([Category(e) for e in self._subcats_recursive],
                              key=lambda cat: tuple(crumb.sort_name for crumb in cat.breadcrumb))

            # get all the subcategories, with only the first subdir added

            # number of path components to ingest
            parts = len(self.path.split('/')) + 1 if self.path else 1

            # convert the subcategories into separated pathlists with only 'parts'
            # parts
            subcats = [c.split('/')[:parts] for c in self._subcats_recursive]

            # join them back into a path, and make unique
            subcats = {'/'.join(c) for c in subcats}

            # convert to a bunch of Category objects
            return sorted([Category(c) for c in subcats], key=lambda c: c.sort_name)

        return utils.CallableProxy(_get_subcats)

    @cached_property
    def first(self):
        """ Returns the first entry in the category.

        Takes optional view arguments.
        """
        def _first(**spec):
            """ Get the earliest entry in this category, optionally including subcategories """
            for record in self._entries(spec).order_by(model.Entry.local_date,
                                                       model.Entry.id)[:1]:
                return entry.Entry(record)
            return None

        return utils.CallableProxy(_first)

    @cached_property
    def last(self):
        """ Returns the last entry in the category.

        Takes optional view arguments.
        """
        def _last(**spec):
            """ Get the latest entry in this category, optionally including subcategories """
            for record in self._entries(spec).order_by(orm.desc(model.Entry.local_date),
                                                       orm.desc(model.Entry.id))[:1]:
                return entry.Entry(record)
            return None

        return utils.CallableProxy(_last)

    @cached_property
    def _meta(self):
        if self._record and self._record.file_path:
            return load_metafile(self._record.file_path)

        return None

    @cached_property
    def name(self):
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

        def _name(markup=True, no_smartquotes=False, markdown_extensions=None):
            return markdown.render_title(name, markup, no_smartquotes,
                                         markdown_extensions)
        return utils.CallableProxy(_name)

    @cached_property
    def description(self):
        """ Get the textual description of the category """
        def _description(**kwargs):
            if self._meta:
                return flask.Markup(markdown.to_html(self._meta.get_payload(),
                                                     args=kwargs,
                                                     search_path=self.search_path))
            return None

        if self._meta and self._meta.get_payload():
            return utils.TrueCallableProxy(_description)
        return utils.CallableProxy(None)

    @cached_property
    def search_path(self):
        """ Get the image search path for the category """
        return [os.path.join(config.content_folder, self.path)]

    @cached_property
    def breadcrumb(self):
        """ Get the category hierarchy leading up to this category, including
        root and self.

        For example, path/to/long/category will return a list containing
        Category('path'), Category('path/to'), and Category('path/to/long').
        """
        ret = []
        here = self
        while here:
            ret.append(here)
            here = here.parent
        return list(reversed(ret))

    @cached_property
    def sort_name(self):
        """ Get the sorting name of this category """
        if self._record and self._record.sort_name:
            return self._record.sort_name
        return self.name(markup=False)

    @cached_property
    def tags(self):
        """ Get the list of tags associated with this category's entries.

        Takes optional view arguments (including recurse)

        Returns a list of category.TagCount tuples like `(tag='foo', count=5)`
        """
        def _tags(**spec):
            entries = self._entries(spec)
            tags = orm.select((tag.key, orm.count(tag.key, distinct=False))
                              for e in entries for tag in e.tags)
            return [TagCount(key, count) for (key, count) in tags]
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
    def parent(self):
        """ Get the parent category """
        if self.path:
            return Category(os.path.dirname(self.path))
        return None

    @cached_property
    def root(self):
        """ Get the root category object. Equivalent to `breadcrumb[0]` but faster/easier. """
        if self.path:
            return Category(None)
        return self

    def _entries(self, spec):
        """ Return a model query to get our entry records """
        return queries.build_query({**spec, 'category': self})


@orm.db_session(immediate=True)
def scan_file(fullpath, relpath):
    """ scan a file and put it into the index """

    load_metafile.cache_clear()

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
        path_alias.set_alias(alias, category=record)

    orm.commit()

    return record
