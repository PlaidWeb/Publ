# cards.py
""" Rendering functions for Twitter/OpenGraph cards"""

import logging

import misaka

from . import image, utils

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


class CardData():
    """ Extracted card data """
    # pylint: disable=too-few-public-methods

    def __init__(self):
        self.description = None
        self.image = None


class CardParser(misaka.BaseRenderer):
    """ Customized Markdown renderer for parsing out information for a card """

    def __init__(self, out, config, image_search_path):
        super().__init__()

        self._config = {**config, 'absolute': True}
        self._image_search_path = image_search_path

        self._out = out

    def paragraph(self, content):
        """ Turn the first paragraph of text into the summary text """
        if not self._out.description:
            print('----content-----', content)
            self._out.description = content.strip()
        return ' '

    def image(self, raw_url, title='', alt=''):
        """ Extract the first image """
        if self._out.image:
            # We already have an image, so we can abort
            return ' '

        image_specs = raw_url
        if title:
            image_specs += ' "{}"'.format(title)

        _, container_args = image.parse_alt_text(alt)

        spec_list = image.get_spec_list(image_specs, container_args)

        for spec in spec_list:
            if not spec:
                continue

            self._out.image = self._render_image(spec, alt)
            if self._out.image:
                break

        return ' '

    @staticmethod
    def link(content, link, title=''):
        """ extract the text content out of a link """
        # pylint: disable=unused-argument

        return content

    def _render_image(self, spec, alt=''):
        """ Given an image spec, try to turn it into a card image per the configuration """
        # pylint: disable=unused-argument

        try:
            path, image_args, _ = image.parse_image_spec(spec)
        except Exception as err:  # pylint: disable=broad-except
            # we tried™
            logger.exception("Got error on spec %s: %s", spec, err)
            return None

        if path.startswith('@'):
            # static image resource
            return utils.static_url(path[1:], absolute=True)

        if path.startswith('//') or '://' in path:
            # remote image
            return path

        img = image.get_image(path, self._image_search_path)
        if img:
            image_config = {**image_args, **self._config}
            return utils.static_url(img.get_rendition(1, image_config)[0], absolute=True)

        return None


def extract_card(text, config, image_search_path):
    """ Extract card data based on the provided texts. """
    card = CardData()
    parser = CardParser(card, config, image_search_path)
    misaka.Markdown(parser)(text)

    return card
