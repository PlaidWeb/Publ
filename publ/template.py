# template.py
""" Wrapper for template information """

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

        # Flask expects template filenames to be /-separated regardless of
        # platform
        if os.sep != '/':
            self.filename = '/'.join(os.path.normpath(filename).split(os.sep))
        else:
            self.filename = filename

        self.file_path = file_path
        self.mtime = os.stat(file_path).st_mtime
        self.last_modified = arrow.get(self.mtime)

    def __str__(self):
        return self.name

    def _key(self):
        return Template, self.file_path

    def __repr__(self):
        return repr(self._key())

    def __hash__(self):
        return hash(self._key())
