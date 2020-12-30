""" test framework stuff """

import uuid

import flask

from publ import config


class PublMock(flask.Flask):
    """ A mock class for a Publ app """

    def __init__(self, cfg: dict = None, **kwargs):
        super().__init__(__name__, **kwargs)
        self.publ_config = config.Config(cfg or {})
        self.secret_key = uuid.uuid4().bytes
