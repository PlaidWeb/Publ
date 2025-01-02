# template.py
""" Wrapper for template information """

import fnmatch
import glob
import hashlib
import logging
import mimetypes
import os
import typing

import arrow
import flask
import werkzeug.exceptions as http_error

from . import image, utils
from .config import config

LOGGER = logging.getLogger(__name__)

BUILTIN_DIR = os.path.join(os.path.dirname(__file__), 'default_template')

# A useful set of default priorities for clients that don't declare Accept (e.g. curl)
DEFAULT_ACCEPT = ['text/html',
                  'application/rss+xml',
                  'application/atom+xml',
                  'application/xml',
                  'style/css',
                  'text/plain',
                  '*/*']


class Template:
    """ Template information wrapper """
    # pylint: disable=too-few-public-methods,too-many-instance-attributes

    def __init__(self, name: str, filename: str, file_path: typing.Optional[str],
                 content: typing.Optional[str] = None,
                 mime_type: typing.Optional[str] = None):
        """ Useful information for the template object:

        name -- The name of the template
        filename -- The filename of the template
        file_path -- The full path to the template
        content -- static content
        """
        # pylint:disable=too-many-arguments,too-many-positional-arguments
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

        self.mime_type = mime_type if mime_type else mimetypes.guess_type(filename)[0]

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

    def image(self, filename):
        """ Retrieve an image using our search path as the context """
        search_path = (os.path.join(config.content_folder, os.path.dirname(self.filename)),)
        return image.get_image(filename, search_path)


def map_template(category: str,
                 template_list: typing.Union[str, typing.List[str]],
                 in_exception=False
                 ) -> typing.Optional[Template]:
    """
    Given a file path and an acceptable list of templates, return the
    best-matching template's path relative to the configured template
    directory.

    Arguments:

    category -- The path to map
    template_list -- A template to look up (as a string), or a list of templates.
    """
    # pylint:disable=too-many-locals,too-many-branches

    # get the sorted acceptance list
    accept_mime = [mime for (mime, _) in flask.request.accept_mimetypes]
    if in_exception:
        accept_mime.append('*/*')

    # Clients which accept *anything* (e.g. curl) should be forced into a more
    # sensible priority order
    if not accept_mime or accept_mime == ['*/*']:
        accept_mime = DEFAULT_ACCEPT

    # Get the MIME types that are also just glob matches
    accept_glob = [mime for mime in accept_mime if '*' in mime]

    LOGGER.debug("accept_mime: %s", accept_mime)
    LOGGER.debug("accep_glob: %s", accept_glob)

    # gets a list like [('foo/bar', ['.foo','.bar'])]
    mime_exts = [(None, [''])] + [(mime, mimetypes.guess_all_extensions(mime))
                                  for mime in accept_mime]

    # unpacks it to [('foo/bar', '.foo'), ('foo/bar', '.bar')]
    extensions = [(mime, ext) for mime, exts in mime_exts for ext in exts]

    LOGGER.debug("Extension priority: %s", extensions)

    could_glob = False

    for template in utils.as_list(template_list):
        path: typing.Optional[str] = os.path.normpath(category)
        while path is not None:
            LOGGER.debug("checking path %s for template %s", path, template)
            for mime, extension in extensions:
                LOGGER.debug('path=%s mime=%s extension=%s', path, mime, extension)
                candidate = os.path.join(path, template + extension)
                file_path = os.path.join(config.template_folder, candidate)
                if os.path.isfile(file_path):
                    # Note that if the template is called out directly, this will
                    # not check if it matches the Accept: header. This technically
                    # violates HTTP but in any situation where the name is given
                    # directly there's almost certainly a */* in place.
                    #
                    # Properly checking Accept: in this context would be super annoying.
                    return Template(template, candidate, file_path,
                                    mime_type=mime)

            # check for glob matches
            glob_candidate = os.path.join(path, f'{template}.*')
            glob_files = glob.glob(glob_candidate, root_dir=config.template_folder)
            if glob_files:
                could_glob = True

            for pattern in accept_glob:
                for candidate in glob_files:
                    cmime, _ = mimetypes.guess_type(candidate)
                    if pattern == '*/*' or (cmime and fnmatch.fnmatch(cmime, pattern)):
                        LOGGER.debug("Found glob match: %s (%s)", candidate, cmime)
                        return Template(template, candidate,
                                        os.path.join(config.template_folder, candidate))

            parent = os.path.dirname(path)
            if parent != path:
                path = parent
            else:
                path = None

    # We didn't find one in the filesystem, so let's consult the builtins instead
    for template in utils.as_list(template_list):
        for mime, extension in extensions:
            filename = template + extension
            template_string = _get_builtin(filename)
            if template_string:
                return Template(template, filename, None,
                                content=template_string, mime_type=mime)

        # check for glob matches
        glob_files = glob.glob(f'{template}.*', root_dir=BUILTIN_DIR)
        if glob_files:
            could_glob = True

        for pattern in accept_glob:
            for candidate in glob_files:
                cmime, _ = mimetypes.guess_type(candidate)
                if cmime and fnmatch.fnmatch(cmime, pattern):
                    return Template(template, candidate, None, content=_get_builtin(candidate))

    if could_glob:
        # A precise match wasn't found, but could have been if there were a broader acceptance
        raise http_error.NotAcceptable(f"Could not find match for {accept_mime}")

    return None


def _get_builtin(filename: str) -> typing.Optional[str]:
    """ Get a builtin template """

    builtin_file = os.path.join(BUILTIN_DIR, filename)
    if os.path.isfile(builtin_file):
        with open(builtin_file, 'r', encoding='utf-8') as file:
            return file.read()

    return None
