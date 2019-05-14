# cards.py
""" Rendering functions for Twitter/OpenGraph cards"""

import logging

import misaka

from . import image, config

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


class CardData():
    """ Extracted card data """
    # pylint: disable=too-few-public-methods

    def __init__(self):
        self.description = None
        self.images = []


class CardParser(misaka.BaseRenderer):
    """ Customized Markdown renderer for parsing out information for a card """

    def __init__(self, out, args, image_search_path):
        super().__init__()

        self._config = {**args, 'absolute': True}
        self._image_search_path = image_search_path

        self._out = out

    def paragraph(self, content):
        """ Turn the first paragraph of text into the summary text """
        if not self._out.description:
            self._out.description = content
        return ' '

    def image(self, raw_url, title='', alt=''):
        ''' extract the images '''
        max_images = self._config.get('count')
        if max_images is not None and len(self._out.images) >= max_images:
            # We already have enough images, so bail out
            return ' '

        image_specs = raw_url
        if title:
            image_specs += ' "{}"'.format(title)

        alt, container_args = image.parse_alt_text(alt)

        spec_list, _ = image.get_spec_list(image_specs, container_args)

        for spec in spec_list:
            if not spec:
                continue

            self._out.images.append(self._render_image(spec, alt))
            if max_images is not None and len(self._out.images) >= max_images:
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

        img = image.get_image(path, self._image_search_path)
        if img:
            image_config = {**image_args, **self._config, 'absolute': True}
            return img.get_rendition(1, **image_config)[0]

        return None


def extract_card(text, args, image_search_path):
    """ Extract card data based on the provided texts. """
    card = CardData()
    parser = CardParser(card, args, image_search_path)
    misaka.Markdown(parser,
                    extensions=args.get('markdown_extensions')
                    or config.markdown_extensions
                    )(text)

    return card
