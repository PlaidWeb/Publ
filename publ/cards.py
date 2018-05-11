# cards.py
""" Rendering functions for Twitter/OpenGraph cards"""

import misaka
import flask

from . import image, utils


class CardData():
    """ Extracted card data """

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

        alt, container_args = image.parse_alt_text(alt)

        spec_list = [spec.strip() for spec in image_specs.split('|')]

        if 'count' in container_args:
            if 'count_offset' in container_args:
                spec_list = spec_list[container_args['count_offset']:]
            spec_list = spec_list[:container_args['count']]

        for spec in spec_list:
            if not spec:
                continue

            self._out.image = self._render_image(spec, alt)
            if self._out.image:
                break

        return ' '

    def link(self, content, link, title=''):
        return content

    def _render_image(self, spec, alt):
        """ Given an image spec, try to turn it into a card image per the configuration """
        try:
            path, image_args, title = image.parse_image_spec(spec)
        except Excpetion as err:  # pylint: disable=broad-except
            # we tried™
            return None

        if path.startswith('@'):
            # static image resource
            return utils.static_url(path[1:], absolute=True)

        if path.startswith('//') or '://' in path:
            # remote image
            return path

        img = image.get_image(path, self._image_search_path)
        if img:
            return utils.static_url(img.get_rendition(1, self._config)[0], absolute=True)

        return None


def extract_card(text, config, image_search_path):
    """ Extract card data based on the provided texts. """
    card = CardData()
    parser = CardParser(card, config, image_search_path)
    misaka.Markdown(parser)(text)

    return card
