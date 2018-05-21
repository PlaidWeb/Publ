# category.py
""" The Category object passed to entry and category views """

from __future__ import absolute_import

import os
import logging
import email
import functools

import flask
from flask import url_for
from werkzeug.utils import cached_property

from . import model
from . import utils
from . import entry  # pylint: disable=cyclic-import
from . import queries
from . import path_alias
from . import markdown
from . import config

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


@functools.lru_cache(10)
def load_metafile(filepath):
    """ Load a metadata file from the filesystem """
    try:
        with open(filepath, 'r') as file:
            return email.message_from_file(file)
    except FileNotFoundError:
        logger.warning("Category file %s not found", filepath)
        model.Category.delete().where(model.Category.file_path == filepath).execute()

    return None


class Category:
    """ Wrapper for category information """
    # pylint: disable=too-few-public-methods,too-many-instance-attributes

    def __init__(self, path):
        """ Initialize a category wrapper

        path -- the path to the category
        """

        self.path = path
        self.basename = os.path.basename(path)

        subcat_query = model.Entry.select(model.Entry.category).distinct()
        if path:
            subcat_query = subcat_query.where(
                model.Entry.category.startswith(path + '/'))
        else:
            subcat_query = subcat_query.where(model.Entry.category != path)

        self._subcats_recursive = subcat_query.order_by(model.Entry.category)

        self.link = utils.CallableProxy(self._link)

        self.subcats = utils.CallableProxy(self._get_subcats)
        self.first = utils.CallableProxy(self._first)
        self.last = utils.CallableProxy(self._last)

        self._record = model.Category.get_or_none(
            model.Category.category == path)

    @cached_property
    def _meta(self):
        if self._record and self._record.file_path:
            return load_metafile(self._record.file_path)

        return None

    @cached_property
    def name(self):
        """ Get the display name of the category """
        if self._meta and self._meta.get('name'):
            # get it from the meta file
            return self._meta.get('name')
        # infer it from the basename
        return self.basename.replace('_', ' ').title()

    @cached_property
    def description(self):
        """ Get the textual description of the category """
        if self._meta and self._meta.get_payload():
            return utils.TrueCallableProxy(self._description)
        return utils.CallableProxy(None)

    @cached_property
    def image_search_path(self):
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

    def _description(self, **kwargs):
        if self._meta:
            return flask.Markup(markdown.to_html(self._meta.get_payload(), config=kwargs,
                                                 image_search_path=self.image_search_path))
        return None

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

    def _link(self, template='', absolute=False):
        return url_for('category',
                       category=self.path,
                       template=template,
                       _external=absolute)

    def __str__(self):
        return self.path

    def __eq__(self, other):
        if isinstance(other, str):
            return other == self.path
        return other.path == self.path

    def __hash__(self):
        return hash(self.path)

    def __lt__(self, other):
        return self.path < other.path

    @cached_property
    def parent(self):
        """ Get the parent category """
        if self.path:
            return Category(os.path.dirname(self.path))
        return None

    def _get_subcats(self, recurse=False):
        """ Get the subcategories of this category

        recurse -- whether to include their subcategories as well
        """

        if recurse:
            # No need to filter
            return [Category(e.category) for e in self._subcats_recursive]

        # get all the subcategories, with only the first subdir added

        # number of path components to ingest
        parts = len(self.path.split('/')) + 1 if self.path else 1

        # get the subcategories
        subcats = [e.category for e in self._subcats_recursive]

        # convert them into separated pathlists with only 'parts' parts
        subcats = [c.split('/')[:parts] for c in subcats]

        # join them back into a path, and make unique
        subcats = {'/'.join(c) for c in subcats}

        # convert to a bunch of Category objects
        return [Category(c) for c in sorted(subcats)]

    def _entries(self, spec):
        """ Return a model query to get our entry records """
        return model.Entry.select().where(
            queries.build_query({**spec, 'category': self}))

    def _first(self, **spec):
        """ Get the earliest entry in this category, optionally including subcategories """
        return entry.Entry(self._entries(spec).order_by(
            model.Entry.local_date, model.Entry.id).get())

    def _last(self, **spec):
        """ Get the latest entry in this category, optionally including subcategories """
        return entry.Entry(self._entries(spec).order_by(
            -model.Entry.local_date, -model.Entry.id).get())


def scan_file(fullpath, relpath):
    """ scan a file and put it into the index """

    load_metafile.cache_clear()

    meta = load_metafile(fullpath)
    if not meta:
        return True

    with model.lock:
        # update the category meta file mapping
        category = meta.get('Category', os.path.dirname(relpath))
        values = {
            'file_path': fullpath,
        }

        logger.debug("setting category %s to metafile %s", category, fullpath)
        record, created = model.Category.get_or_create(category=category,
                                                       defaults=values)
        if not created:
            record.update(**values).where(model.Category.id ==
                                          record.id).execute()

        # update other relationships to the index
        for alias in meta.get_all('Path-Alias', []):
            path_alias.set_alias(alias, category=record)

    return record
