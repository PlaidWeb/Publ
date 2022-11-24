# cards.py
""" Rendering functions for Twitter/OpenGraph cards"""

import logging
import typing

from . import utils

LOGGER = logging.getLogger(__name__)


class CardData():
    """ Extracted card data """
    # pylint: disable=too-few-public-methods

    def __init__(self) -> None:
        self.images: typing.List[
            typing.Tuple[
                str,
                typing.Optional[str],
                typing.Optional[str]]] = []


class HtmlCardParser(utils.HTMLTransform):
    """ Parse the card data out of an HTML document """

    def __init__(self, card):
        super().__init__()

        self._card = card
        self._images = []

    def handle_starttag(self, tag, attrs):
        if tag == 'img':
            src = None
            width = None
            height = None
            for attr, val in attrs:
                if attr == 'src':
                    src = val
                elif attr == 'width':
                    width = val
                elif attr == 'height':
                    height = val
            if src:
                self._card.images.append((src, width, height))


def extract_card(html_text: str) -> CardData:
    """ Extract card data based on the provided HTML. """
    card = CardData()
    HtmlCardParser(card).feed(html_text)

    return card
