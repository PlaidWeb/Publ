""" Bearer token tests """
# pylint:disable=missing-docstring

import flask
import pytest
import werkzeug.exceptions as http_error

from publ import tokens, user


def test_token_flow(mocker):
    app = flask.Flask(__name__)
    app.secret_key = 'random bytes'
    mock_time = mocker.patch('time.time')

    with app.app_context():
        mock_time.return_value = 100
        token = tokens.get_token('somebody', 1600)

        parsed = tokens.parse_token(token)
        assert parsed['me'] == 'somebody'
        assert 'scope' not in parsed

        mock_time.return_value = 1800
        with pytest.raises(http_error.Unauthorized):
            parsed = tokens.parse_token(token)

        token = tokens.get_token('someone', 1600, 'read')
        parsed = tokens.parse_token(token)
        assert parsed['me'] == 'someone'
        assert parsed['scope'] == 'read'

        with pytest.raises(http_error.Unauthorized):
            parsed = tokens.parse_token('kwijibo')


def test_request():
    app = flask.Flask(__name__)

    with app.test_request_context('/foo'):
        tokens.request(user.User('moo'))
        assert 'needs_auth' not in flask.g

    with app.test_request_context('/bar'):
        tokens.request(None)
        assert flask.g.needs_auth
