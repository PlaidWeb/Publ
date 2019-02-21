# links.py
""" Functions for manipulating outgoing HTML links """

from . import image
from . import utils


def remap_path(path, search_path, absolute=False):
    """ Remap a link or source target to an appropriate entry or image rendition """

    # Remote or static URL: do the thing
    if not path.startswith('//') and not '://' in path:
        path, sep, anchor = path.partition('#')
        entry = utils.find_entry(path, search_path)
        if entry:
            return entry.permalink(absolute=absolute) + sep + anchor

    # Image URL: do the thing
    img_path, img_args, _ = image.parse_image_spec(path)
    img = image.get_image(img_path, search_path)
    if isinstance(img, image.LocalImage):
        path, _ = img.get_rendition(**img_args)

    return utils.remap_link_target(path, absolute)
