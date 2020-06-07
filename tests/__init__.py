""" test framework stuff """

import flask

from publ import config


class PublMock(flask.Flask):
    """ A mock class for a Publ app """

    def __init__(self, cfg: dict = None):
        super().__init__(__name__)
        self.publ_config = config.Config(cfg or {})

