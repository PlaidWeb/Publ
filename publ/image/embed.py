""" Mechanism for getting embed data from an external URL """

import functools
import logging
import urllib.parse

import requests

from ..caching import cache

LOGGER = logging.getLogger(__name__)


@functools.lru_cache()
@cache.memoize()
def get_embed_data(url: str, mime_type: str = None) -> tuple:
    """ Get the embed data for the URL.

    Returns a tuple of (tag, tag_attrs, inner_html)

    :param str url: The URL of the resource to embed

    :param str mime_type: The MIME type of the resource, if already known
    """

    parsed = urllib.parse.urlparse(url)
    LOGGER.debug('%s -> %s', url, parsed)

    if 'youtube.com' in parsed.netloc or 'youtu.be' in parsed.netloc:
        query = urllib.parse.parse_qs(parsed.query)
        vid = query.get('v', parsed.path[1:])
        toff = query.get('t')

        attrs = {'width': 560,
            'height': 315,
                 'allow': 'accelerometer; autoplay; encrypted-media; picture-in-picture',
                 'allowfullscreen': None
                 }

        src = f'https://www.youtube.com/embed/{vid}'
        if toff:
            src += f'?t={toff}'

        attrs['src'] = src

        return 'iframe', attrs, ''

    request = None
    if not mime_type:
        LOGGER.debug("Getting MIME type for %s", url)
        request = requests.head(url)
        url = request.url
        mime_type = request.headers.get('content-type', '')
    LOGGER.debug("%s: mimetype=%s", url, mime_type)

    if mime_type and 'image/' in mime_type:
        return 'img', {'src': url}, ''

    if mime_type and 'video/' in mime_type:
        return 'video', {'src': url, 'controls': None}, ''

    if mime_type and 'audio/' in mime_type:
        return 'audio', {'src': url, 'controls': None}, ''

    if mime_type and (mime_type.startswith('text/html') or mime_type.startswith('text/xhtml')):
        LOGGER.debug("trying to grok HTML page %s", url)
        #request = requests.get(url)
        # TODO: parse opengraph/twittercard

    # we don't know what it is so just present it as an iframe
    return 'iframe', {'src': url}, ''
