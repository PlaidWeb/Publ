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

    def ticket_endpoint(request, _):
        import urllib.parse
        args = urllib.parse.parse_qs(request.text)
        assert 'subject' in args
        assert 'ticket' in args
        assert 'resource' in args
        stash['ticket'] = args['ticket']

        with app.test_client() as client:
            req = client.post(token_endpoint, data={
                'grant_type': 'ticket',
                'ticket': args['ticket']
            })
            token = json.loads(req.data)
            assert 'access_token' in token
            assert token['token_type'].lower() == 'bearer'
            stash['response'] = token

    with app.test_request_context('/'):
        token_endpoint = flask.url_for('tokens')

    foo_tickets = requests_mock.get('https://foo.example/', text='''
        <link rel="ticket_endpoint" href="https://foo.example/tickets">
        <p class="h-card"><span class="p-name">boop</span></p>
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

        assert foo_tickets.call_count == 1
        assert stash['response']['token_type'].lower() == 'bearer'
        assert stash['response']['me'] == 'https://foo.example/'
        token = tokens.parse_token(stash['response']['access_token'])
        assert token['me'] == 'https://foo.example/'

        req = client.get(token_endpoint, headers={
            'Authorization': f'Bearer {stash["response"]["access_token"]}'
        })
        assert req.status_code == 200
        assert req.headers['Content-Type'] == 'application/json'
        verified = json.loads(req.data)
        assert verified['me'] == 'https://foo.example/'

    token_user = user.User(verified['me'])
    assert token_user.profile['name'] == 'boop'

    # Provisional request flow
    with app.test_request_context('/bogus'):
        request_url = flask.url_for('tokens')
    with app.test_client() as client:
        req = client.post(request_url, data={'action': 'ticket',
                                             'subject': 'https://foo.example'})
        LOGGER.info("Got ticket redemption response %d: %s",
                    req.status_code, req.data)
        assert req.status_code == 202
        assert req.data == b'Ticket sent'

        # should be cached from previous test
        assert foo_tickets.call_count == 1
        assert stash['response']['token_type'].lower() == 'bearer'
        assert stash['response']['me'] == 'https://foo.example/'
        token = tokens.parse_token(stash['response']['access_token'])
        assert token['me'] == 'https://foo.example/'

        req = client.get(token_endpoint, headers={
            'Authorization': f'Bearer {stash["response"]["access_token"]}'
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
        assert bar_tickets.called  # page still needs to be retrieved to get the profile
        assert stash['response']['token_type'].lower() == 'bearer'
        assert stash['response']['me'] == 'https://bar.example/'
        token = tokens.parse_token(stash['response']['access_token'])
        assert token['me'] == 'https://bar.example/'

        req = client.get(token_endpoint, headers={
            'Authorization': f'Bearer {stash["response"]["access_token"]}'
        })
        assert req.status_code == 200
        assert req.headers['Content-Type'] == 'application/json'
        verified = json.loads(req.data)
        assert verified['me'] == 'https://bar.example/'

    # Attempt to redeem a token as if it were a ticket
    with app.test_request_context():
        req = client.post(token_endpoint, data={
            'grant_type': 'ticket',
            'ticket': stash['response']['access_token']})
        assert req.status_code == 401

    # Redeem the refresh_token
    with app.test_client() as client:
        req = client.post(token_endpoint, data={
            'grant_type': 'refresh_token',
            'refresh_token': stash['response']['refresh_token']
        })
        assert req.status_code == 200
        assert req.headers['Content-Type'] == 'application/json'
        refreshed = json.loads(req.data)
        assert refreshed['me'] == 'https://bar.example/'

    # Verify that redemption of a plain token fails
    with app.test_client() as client:
        req = client.post(token_endpoint, data={
            'grant_type': 'refresh_token',
            'refresh_token': stash['response']['access_token']
        })
        assert req.status_code == 401

    # Verify that a ticket can't be used as a bearer token
    with app.test_client() as client:
        req = client.get(token_endpoint, headers={
            'Authorization': f'Bearer {stash["ticket"]}'
        })
        assert req.status_code == 401

    # Verify that a refresh_token can't be used as a bearer token
    with app.test_client() as client:
        req = client.get(token_endpoint, headers={
            'Authorization': f'Bearer {stash["response"]["refresh_token"]}'
        })
        assert req.status_code == 401


def test_ticketauth_canonical(requests_mock):
    """
        Ensure that rel="canonical" is being correctly respected on TicketAuth grants,
        and that identity URLs are being properly canonicalized
    """
    app = PublMock()
    app.add_url_rule('/_tokens', 'tokens', tokens.indieauth_endpoint,
                     methods=['GET', 'POST'])

    stash = {}

    def ticket_endpoint(request, _):
        import urllib.parse
        args = urllib.parse.parse_qs(request.text)
        assert 'subject' in args
        assert 'ticket' in args
        assert 'resource' in args
        stash['ticket'] = args['ticket']

        with app.test_client() as client:
            req = client.post(token_endpoint, data={
                'grant_type': 'ticket',
                'ticket': args['ticket']
            })
            token = json.loads(req.data)
            assert 'access_token' in token
            assert token['token_type'].lower() == 'bearer'
            stash['response'] = token

    with app.test_request_context('/'):
        token_endpoint = flask.url_for('tokens')

    for scheme in ('http', 'https'):
        requests_mock.get(f'{scheme}://canonical.ticketauth', text='''
            <link rel="ticket_endpoint" href="https://foo.example/tickets">
            <link rel="canonical" href="https://canonical.ticketAuth">
            <p class="h-card"><span class="p-name">pachelbel</span></p>
            ''')
    requests_mock.post('https://foo.example/tickets', text=ticket_endpoint)

    def test_url(identity, match):
        with app.test_request_context('/bogus'):
            request_url = flask.url_for('tokens')
        with app.test_client() as client:
            req = client.post(request_url, data={'action': 'ticket',
                                                 'subject': identity})
            LOGGER.info("Got ticket redemption response %d: %s",
                        req.status_code, req.data)
            assert req.status_code == 202
            assert req.data == b'Ticket sent'

            assert stash['response']['token_type'].lower() == 'bearer'
            assert stash['response']['me'] == match
            token = tokens.parse_token(stash['response']['access_token'])
            assert token['me'] == match

            req = client.get(token_endpoint, headers={
                'Authorization': f'Bearer {stash["response"]["access_token"]}'
            })
            assert req.status_code == 200
            assert req.headers['Content-Type'] == 'application/json'
            verified = json.loads(req.data)
            assert verified['me'] == match

            token_user = user.User(verified['me'])
            assert token_user.profile['name'] == 'pachelbel'

    for url in ('http://canonical.ticketauth', 'https://canonical.ticketauth',
                'http://Canonical.TicketAuth'):
        test_url(url, 'https://canonical.ticketauth/')
