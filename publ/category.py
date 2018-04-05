# category.py
# The Category object passed to entry and category views

from . import model
from . import utils
from flask import url_for

import os

class CategoryLink(utils.SelfStrCall):
    def __init__(self, category):
        self.category = category

    def __call__(self, template=''):
        return url_for('category', category=self.category, template=template)

class Category:
    def __init__(self, path):
        self.path = path
        self.basename = os.path.basename(path)

        # the falsiness of '' makes this hard to express as a one-liner
        if path == '':
            self._parent = None
        else:
            self._parent = os.path.dirname(path)

        subcat_query = model.Entry.select(model.Entry.category).distinct()
        if path:
            subcat_query = subcat_query.where(model.Entry.category.startswith(path + '/'))
        else:
            subcat_query = subcat_query.where(model.Entry.category != path)

        self._subcats_recursive = subcat_query
        self._subcats = None

        self.link = CategoryLink(self.path)

    def __str__(self):
        return self.path

    ''' Lazily bind related objects '''
    def __getattr__(self, name):
        if name == 'parent':
            self.parent = (self._parent != None) and Category(self._parent) or None
            return self.parent

        if name == 'subcats':
            # get all the subcategories, with only the first subdir added

            # number of path components to ingest
            parts = self.path and len(self.path.split('/')) + 1 or 1

            # get the subcategories
            subcats = [e.category for e in self._subcats_recursive]

            # convert them into separated pathlists with only 'parts' parts
            subcats = [c.split('/')[:parts] for c in subcats]

            # join them back into a path, and make unique
            subcats = {'/'.join(c) for c in subcats}

            # convert to a bunch of Category objects and bind to the Category
            self.subcats = [Category(c) for c in subcats]
            return self.subcats

        if name == 'subcats_recursive':
            # convert the recursive subcats query to a property
            self.subcats_recursive = [Category(e.category) for e in self._subcats_recursive]
            return self.subcats_recursive
