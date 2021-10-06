""" test framework stuff """

import logging
import uuid

import flask

from publ import config

logging.basicConfig(level=logging.DEBUG)
logging.getLogger().setLevel(logging.DEBUG)


class MockIndexer():
    """ Mock out the indexer for test purposes """
    # pylint:disable=too-few-public-methods
    @staticmethod
    def submit(func, *args, **kwargs):
        """ fake background submission that just runs immediately """
        func(*args, **kwargs)


class PublMock(flask.Flask):
    """ A mock class for a Publ app """

    def __init__(self, cfg: dict = None, **kwargs):
        super().__init__(__name__, **kwargs)
        self.publ_config = config.Config(cfg or {})
        self.secret_key = uuid.uuid4().bytes
        self.indexer = MockIndexer()
