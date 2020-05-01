# cards.py
""" Rendering functions for Twitter/OpenGraph cards"""

import logging
import typing

import flask

from . import utils

LOGGER = logging.getLogger(__name__)


class CardData():
    """ Extracted card data """
    # pylint: disable=too-few-public-methods

    def __init__(self):
        self.description: typing.Optional[str] = None
        self.images: typing.List[
            typing.Tuple[
                str,
                typing.Optional[str],
                typing.Optional[str]]] = []

    def commit(self):
        """ Apply all finalization to the card data """
        if self.description:
            self.description = flask.Markup(self.description.strip())


class HtmlCardParser(utils.HTMLTransform):
    """ Parse the first paragraph out of an HTML document """

    def __init__(self, card):
        super().__init__()

        self._consume = True
        self._card = card
        self._images = []

    def handle_starttag(self, tag, attrs):
        # pylint:disable=unused-argument
        if tag == 'p' and self._card.description:
            # We already got some data, so this is a malformed/old-style document
            self._consume = False
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

    def handle_endtag(self, tag):
        if tag == 'p':
            self._consume = False

    def handle_data(self, data):
        if self._consume:
            if not self._card.description:
                self._card.description = ''
            self._card.description += data


def extract_card(html_text: str) -> CardData:
    """ Extract card data based on the provided HTML. """
    card = CardData()
    HtmlCardParser(card).feed(html_text)
    card.commit()

    return card
