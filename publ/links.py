# links.py
""" Functions for manipulating outgoing HTML links """

import os
import re
import typing
from urllib.parse import urljoin

from flask import request

from . import entry  # pylint:disable=cyclic-import
from . import image, model, utils
from .config import config


def resolve(path: str, search_path: typing.Tuple[str, ...], absolute: bool = False) -> str:
    """ Remap a link or source target to an appropriate entry or image rendition """

    # Resolve external URLs
    if re.match(r'([a-z][a-z0-9+.\-]*:)?//', path, re.I):
        return path

    # Resolve static assets
    if path.startswith('@'):
        return utils.static_url(path[1:], absolute)

    path, sep, anchor = path.partition('#')

    # Resolve entries
    found = find_entry(path, search_path)
    if found:
        return entry.Entry.load(found).permalink(absolute=absolute) + sep + anchor

    # Resolve images and assets
    img_path, img_args, _ = image.parse_image_spec(path)
    img = image.get_image(img_path, search_path)
    if not isinstance(img, image.ImageNotFound):
        path, _ = img.get_rendition(**{**img_args, 'absolute': absolute})

    # We don't know what this is, so just treat it like a normal URL.
    if absolute:
        path = urljoin(request.url, path)

    return path + sep + anchor


def find_entry(rel_path: str, search_path: typing.Tuple[str, ...]) -> typing.Optional[model.Entry]:
    """ Find an entry by relative path. Arguments:

    rel_path -- the entry's filename (or entry ID)
    search_path -- a list of directories to check in

    Returns: the resolved Entry object
    """

    try:
        entry_id = int(rel_path)
        record = model.Entry.get(id=entry_id)
        if record:
            return record
    except ValueError:
        pass

    if rel_path.startswith('/'):
        search_path = (config.content_folder,)
        rel_path = '.' + rel_path

    for where in search_path:
        abspath = os.path.normpath(os.path.join(where, rel_path))
        record = model.Entry.get(file_path=abspath)
        if record:
            return record
    return None
