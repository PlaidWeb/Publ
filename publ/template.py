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
                  'application/json',
                  'style/css',
                  'text/plain']


def get_mimetype(fname):
    """
    Get the MIME type of a template, either from the configuration or from
    the Python mimetypes configuration
    """
    LOGGER.debug("get_mimetype(%s)", fname)
    for pattern in (fname, os.path.basename(fname), os.path.splitext(fname)[1]):
        if pattern in config.template_mimetypes:
            return config.template_mimetypes[pattern]

    return mimetypes.guess_type(fname)[0]


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

        self.mime_type = mime_type if mime_type else get_mimetype(filename)

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


def match_glob(mime, patterns):
    """
    Given a precise MIME type and a list of patterns, return the first
    pattern that the MIME type matches
    """

    for pat in patterns:
        if fnmatch.fnmatch(mime, pat):
            return pat

    return None


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

    LOGGER.debug('accept_mimetypes = %s', list(flask.request.accept_mimetypes))

    accept_all = False

    # get the sorted acceptance list.
    # If */* is in the acceptance list, expand it to our default acceptance to
    # still prioritize things reasonably well
    accept_mime: list[str] = []
    for mime, _ in flask.request.accept_mimetypes:
        if mime == '*/*':
            accept_mime += DEFAULT_ACCEPT
            accept_all = True
        elif mime not in accept_mime:
            accept_mime.append(mime)

    # If we're handling an exception, always allow a fallback
    if in_exception:
        accept_all = True

    # Clients which accept *anything* (e.g. curl) should be forced into a more
    # sensible priority order
    if not accept_mime or accept_mime == ['*/*']:
        accept_mime = DEFAULT_ACCEPT
        accept_all = True

    LOGGER.debug("accept_mime: %s", accept_mime)

    def check_path(path, root_dir) -> typing.Union[Template, bool]:
        """
        Checks the path for the template list.

        If an acceptable match is found, returns the template.

        If an acceptable match wasn't found but there was a template that would
        match with a wider Accept filter, returns True.

        Otherwise, returns False.
        """

        could_glob = False

        for template in utils.as_list(template_list):
            LOGGER.debug("checking path %s for template %s", path, template)
            basename = os.path.join(path, template)
            base_path = os.path.join(root_dir, basename)

            # If the template name was given exactly, just return it
            LOGGER.debug("Checking base_path=%s", base_path)
            if os.path.isfile(base_path):
                accept = get_mimetype(basename)
                if (accept_all or
                    accept in accept_mime or
                        match_glob(accept, accept_mime)):
                    LOGGER.debug("Found exact template name match: %s (%s)",
                                 basename, accept)
                    return Template(template, basename, base_path, mime_type=accept)

                # We found this template by name and would have accepted it
                # with a wider filter
                could_glob = True

            # Otherwise, check to see which extensions are available
            template_mimetypes = {
                get_mimetype(fname): fname
                for fname in glob.glob(f'{basename}.*', root_dir=root_dir)
            }

            if not template_mimetypes:
                # No template extensions were found for this template, move on
                # to the next one
                continue

            could_glob = True
            for accept in accept_mime:
                # Check for exact match
                if accept in template_mimetypes:
                    tpath = template_mimetypes[accept]
                    LOGGER.debug("Found exact match: %s -> %s", accept, tpath)
                    return Template(template, tpath,
                                    os.path.join(root_dir, tpath),
                                    mime_type=accept)

                # Check for glob match
                if '*' in accept:
                    for tmime, tpath in template_mimetypes.items():
                        if fnmatch.fnmatch(tmime, accept):
                            LOGGER.debug("Found glob match for: %s -> %s (%s)",
                                         accept, tpath, tmime)
                            return Template(template, tpath,
                                            os.path.join(root_dir, tpath),
                                            mime_type=tmime)

            if accept_all:
                # No standard MIME type was found so we're being weird, just return
                # the first one and call it a day
                for tmime, tpath in template_mimetypes.items():
                    return Template(template, tpath, os.path.join(root_dir, tpath),
                                    mime_type=tmime)

        # No matching template was found for any of the requested template names
        return could_glob

    # Check the template directory hierarchy
    path = os.path.normpath(category)
    could_glob = False
    while True:
        if found := check_path(path, config.template_folder):
            if isinstance(found, Template):
                return found
            could_glob = True

        if (parent := os.path.dirname(path)) == path:
            break
        path = parent

    # Check the builtins
    found = check_path('', BUILTIN_DIR)
    if found:
        if isinstance(found, Template):
            return Template(found.name, found.filename, None, content=_get_builtin(found.filename))
        could_glob = True

    if could_glob:
        # A template would have been found but it was filtered out by our filter
        raise http_error.NotAcceptable(f"Could not find match for {accept_mime}")

    return None


def _get_builtin(filename: str) -> typing.Optional[str]:
    """ Get a builtin template """

    builtin_file = os.path.join(BUILTIN_DIR, filename)
    if os.path.isfile(builtin_file):
        with open(builtin_file, 'r', encoding='utf-8') as file:
            return file.read()

    return None
