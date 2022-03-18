""" Bearer token tests """
# pylint:disable=missing-docstring,too-many-statements

import json
import logging

import flask
import pytest
import werkzeug.exceptions as http_error

from publ import tokens, user

from . import PublMock

LOGGER = logging.getLogger(__name__)


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


def test_ticketauth_flow(requests_mock):
    import authl.disposition
    app = PublMock()
    app.add_url_rule('/_tokens', 'tokens', tokens.indieauth_endpoint,
                     methods=['GET', 'POST'])

    stash = {}

    with app.test_request_context('/'):
        token_endpoint = flask.url_for('tokens')

    def ticket_endpoint(request, _):
        import urllib.parse
        args = urllib.parse.parse_qs(request.text)
        assert 'subject' in args
        assert 'ticket' in args
        assert 'resource' in args

        with app.test_client() as client:
            req = client.post(token_endpoint, data={
                'grant_type': 'ticket',
                'ticket': args['ticket']
            })
            token = json.loads(req.data)
            assert 'access_token' in token
            assert token['token_type'].lower() == 'bearer'
            stash.update(token)

    foo_tickets = requests_mock.get('https://foo.example/', text='''
        <link rel="ticket_endpoint" href="https://foo.example/tickets">
        ''')
    bar_tickets = requests_mock.get('https://bar.example/', text='''
        <link rel="ticket_endpoint" href="https://foo.example/tickets">
        ''')
    requests_mock.post('https://foo.example/tickets', text=ticket_endpoint)

    # Ad-hoc request flow
    with app.test_request_context('/bogus'):
        request_url = flask.url_for('tokens', me='https://foo.example/')
    with app.test_client() as client:
        req = client.get(request_url)
        LOGGER.info("Got ticket redemption response %d: %s",
                    req.status_code, req.data)
        assert req.status_code == 202
        assert req.data == b'Ticket sent'

        assert foo_tickets.called
        assert 'access_token' in stash and stash['token_type'].lower() == 'bearer'
        assert stash['me'] == 'https://foo.example/'
        token = tokens.parse_token(stash['access_token'])
        assert token['me'] == 'https://foo.example/'

        req = client.get(token_endpoint, headers={
            'Authorization': f'Bearer {stash["access_token"]}'
        })
        assert req.status_code == 200
        assert req.headers['Content-Type'] == 'application/json'
        verified = json.loads(req.data)
        assert verified['me'] == 'https://foo.example/'

    # Provisional request flow
    with app.test_request_context('/bogus'):
        request_url = flask.url_for('tokens')
    with app.test_client() as client:
        req = client.post(request_url, data={'action': 'ticket',
                                             'subject': 'https://foo.example/'})
        LOGGER.info("Got ticket redemption response %d: %s",
                    req.status_code, req.data)
        assert req.status_code == 202
        assert req.data == b'Ticket sent'

        assert foo_tickets.called
        assert 'access_token' in stash and stash['token_type'].lower() == 'bearer'
        assert stash['me'] == 'https://foo.example/'
        token = tokens.parse_token(stash['access_token'])
        assert token['me'] == 'https://foo.example/'

        req = client.get(token_endpoint, headers={
            'Authorization': f'Bearer {stash["access_token"]}'
        })
        assert req.status_code == 200
        assert req.headers['Content-Type'] == 'application/json'
        verified = json.loads(req.data)
        assert verified['me'] == 'https://foo.example/'

    # Login flow
    stash.clear()
    with app.test_request_context():
        user.register(authl.disposition.Verified(
            'https://bar.example/',
            '/',
            {'endpoints': {
                'ticket_endpoint': 'https://foo.example/tickets'
            }}))
        assert not bar_tickets.called  # endpoint is already discovered
        assert 'access_token' in stash and stash['token_type'].lower() == 'bearer'
        assert stash['me'] == 'https://bar.example/'
        token = tokens.parse_token(stash['access_token'])
        assert token['me'] == 'https://bar.example/'

        req = client.get(token_endpoint, headers={
            'Authorization': f'Bearer {stash["access_token"]}'
        })
        assert req.status_code == 200
        assert req.headers['Content-Type'] == 'application/json'
        verified = json.loads(req.data)
        assert verified['me'] == 'https://bar.example/'
