# template.py
""" Wrapper for template information """

import hashlib
import os
import typing

import arrow
import flask

from . import utils
from .config import config

EXT_PRIORITY = ['', '.html', '.htm', '.xml', '.json', '.txt']


class Template:
    """ Template information wrapper """
    # pylint: disable=too-few-public-methods

    def __init__(self, name: str, filename: str, file_path: typing.Optional[str],
                 content: typing.Optional[str] = None):
        """ Useful information for the template object:

        name -- The name of the template
        filename -- The filename of the template
        file_path -- The full path to the template
        content -- static content
        """
        self.name = name

        # Flask expects template filenames to be /-separated regardless of
        # platform
        if os.sep != '/':
            self.filename = '/'.join(os.path.normpath(filename).split(os.sep))
        else:
            self.filename = filename

        self.file_path = file_path

        if file_path:
            self.mtime = os.stat(file_path).st_mtime
            self.last_modified = arrow.get(self.mtime)
            self._fingerprint = utils.file_fingerprint(file_path)

        self.content = content
        if content:
            self._fingerprint = hashlib.md5(content.encode('utf-8')).hexdigest()

    def render(self, **args) -> str:
        """ Render the template with the appropriate Flask function """
        if self.content:
            return flask.render_template_string(self.content, **args)
        return flask.render_template(self.filename, **args)

    def __str__(self):
        return self.name

    def _key(self):
        return Template, self.file_path, self._fingerprint

    def __repr__(self):
        return repr(self._key())

    def __hash__(self):
        return hash(self._key())


def map_template(category: str,
                 template_list: typing.Union[str, typing.List[str]]
                 ) -> typing.Optional[Template]:
    """
    Given a file path and an acceptable list of templates, return the
    best-matching template's path relative to the configured template
    directory.

    Arguments:

    category -- The path to map
    template_list -- A template to look up (as a string), or a list of templates.
    """

    for template in utils.as_list(template_list):
        path: typing.Optional[str] = os.path.normpath(category)
        while path is not None:
            for extension in EXT_PRIORITY:
                candidate = os.path.join(path, template + extension)
                file_path = os.path.join(config.template_folder, candidate)
                if os.path.isfile(file_path):
                    return Template(template, candidate, file_path)
            parent = os.path.dirname(path)
            if parent != path:
                path = parent
            else:
                path = None

    # We didn't find one in the filesystem, so let's consult the builtins instead
    for template in utils.as_list(template_list):
        for extension in EXT_PRIORITY:
            filename = template + extension
            template_string = _get_builtin(filename)
            if template_string:
                return Template(template, filename, None, template_string)

    return None


def _get_builtin(filename: str) -> typing.Optional[str]:
    """ Get a builtin template """

    builtin_file = os.path.join(os.path.dirname(__file__), 'default_template', filename)
    if os.path.isfile(builtin_file):
        with open(builtin_file, 'r', encoding='utf-8') as file:
            return file.read()

    return None
