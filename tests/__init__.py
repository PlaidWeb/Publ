""" test framework stuff """

import uuid

import flask

import publ


class PublMock(flask.Flask):
    """ A mock class for a Publ app """

    def __init__(self, cfg: dict = None):
        super().__init__(__name__)
        self.publ_config = publ.config.Config(cfg or {})
        self.secret_key = uuid.uuid4().bytes


def make_app(config):
    """ Build a Publ app for integration test purposes, or testing the app itself """
    app = publ.Publ({'cache': {
        'CACHE_NO_NULL_WARNING': True
        }})
    app.secret_key = uuid.uuid4().bytes
    return app
