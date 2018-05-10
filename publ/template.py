# template.py
""" Wrapper for template information """

from __future__ import absolute_import, with_statement

import os
import arrow


class Template:
    """ Template information wrapper """
    # pylint: disable=too-few-public-methods

    def __init__(self, name, filename, file_path):
        """ Useful information for the template object:

        name -- The name of the template
        filename -- The filename of the template
        file_path -- The full path to the template
        """
        self.name = name
        self.filename = filename
        self.last_modified = arrow.get(os.stat(file_path).st_mtime)

    def __str__(self):
        return self.name
