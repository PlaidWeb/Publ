# links.py
""" Functions for manipulating outgoing HTML links """

import re

from . import image
from . import utils


def resolve(path, search_path, absolute=False):
    """ Remap a link or source target to an appropriate entry or image rendition """

    # Resolve external URLs
    if re.match(r'([a-z][a-z0-9+.\-]*:)?//', path, re.I):
        return path

    # Resolve static assets
    if path.startswith('@'):
        return utils.static_url(path[1:], absolute)

    path, sep, anchor = path.partition('#')

    # Resolve entries
    entry = utils.find_entry(path, search_path)
    if entry:
        return entry.permalink(absolute=absolute) + sep + anchor

    # Resolve images and assets
    img_path, img_args, _ = image.parse_image_spec(path)
    img = image.get_image(img_path, search_path)
    if not isinstance(img, image.ImageNotFound):
        path, _ = img.get_rendition(**{**img_args, 'absolute': absolute})
    return path + sep + anchor
