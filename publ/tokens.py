""" IndieAuth token endpoint """

import json
import logging
import time
import typing

import flask
import itsdangerous
import requests
import werkzeug.exceptions as http_error

from .config import config

LOGGER = logging.getLogger(__name__)


def signer():
    """ Gets the signer/validator for the tokens """
    from .flask_wrapper import current_app
    return itsdangerous.URLSafeSerializer(current_app.secret_key)


def get_token(id_url: str, lifetime: int, scope: str = None) -> str:
    """ Gets a signed token for the given identity"""
    token = {'me': id_url}
    if scope:
        token['scope'] = scope

    return signer().dumps((token, int(time.time() + lifetime)))


def parse_token(token: str) -> typing.Dict[str, str]:
    """ Parse a bearer token to get the stored data """
    try:
        ident, expires = signer().loads(token)
    except itsdangerous.BadData as error:
        LOGGER.error("Got token parse error: %s", error)
        flask.g.token_error = 'Invalid token'  # pylint:disable=assigning-non-slot
        raise http_error.Unauthorized('Invalid token') from error

    if expires < time.time():
        LOGGER.info("Got expired token for %s", ident['me'])
        flask.g.token_error = "Token expired"  # pylint:disable=assigning-non-slot
        raise http_error.Unauthorized("Token expired")

    return ident


def request(user):
    """ Called whenever an authenticated access fails; marks authentication
    as being upgradeable.

    Currently this is unused by Publ itself, but a site can make use of it to
    e.g. add a ``WWW-Authenticate`` header or the like in a post-request hook.
    """

    if not user:
        flask.g.needs_auth = True  # pylint:disable=assigning-non-slot


def send_auth_ticket(subject: str,
                     resource: str,
                     endpoint: str,
                     scope: str = None):
    """ Initiate the TicketAuth flow """
    from .flask_wrapper import current_app

    def _submit():
        scopes = set(scope.split() if scope else [])
        scopes.add('ticket')
        ticket = get_token(subject, config.ticket_lifetime, ' '.join(scopes))

        req = requests.post(endpoint, data={
            'ticket': ticket,
            'resource': resource,
            'subject': subject
        })
        LOGGER.info("Auth ticket sent to %s for %s: %d %s",
                    endpoint, subject, req.status_code, req.text)

    # Use the indexer's threadpool to issue the ticket in the background
    current_app.indexer.submit(_submit)


def indieauth_endpoint():
    """ IndieAuth token endpoint """
    import authl.handlers.indieauth

    if 'me' in flask.request.args:
        # A ticket request is being made
        me_url = flask.request.args['me']
        try:
            endpoint, _ = authl.handlers.indieauth.find_endpoint(me_url,
                                                                 rel='ticket_endpoint')
        except RuntimeError:
            endpoint = None
        if not endpoint:
            raise http_error.BadRequest("Could not get ticket endpoint")
        LOGGER.info("endpoint: %s", endpoint)
        send_auth_ticket(me_url, flask.request.url_root, endpoint)
        return "Ticket sent", 202

    if 'grant_type' in flask.request.form:
        # token grant
        if flask.request.form['grant_type'] == 'ticket':
            # TicketAuth
            if 'ticket' not in flask.request.form:
                raise http_error.BadRequest("Missing ticket")

            ticket = parse_token(flask.request.form['ticket'])
            LOGGER.info("Redeeming ticket for %s; scopes=%s", ticket['me'],
                        ticket['scope'])

            scopes = set(ticket.get('scope', '').split())
            if 'ticket' not in scopes:
                raise http_error.BadRequest("Missing 'ticket' scope")

            scopes.remove('ticket')
            scope = ' '.join(scopes)

            token = get_token(ticket['me'], config.token_lifetime, scope)
            response = {
                'access_token': token,
                'token_type': 'Bearer',
                'me': ticket['me'],
                'expires_in': config.token_lifetime,
                'refresh_token': get_token(ticket['me'],
                                           config.token_lifetime,
                                           ticket['scope'])
            }
            if scope:
                response['scope'] = scope

            return json.dumps(response), {'Content-Type': 'application/json'}

        raise http_error.BadRequest("Unknown grant type")

    if 'action' in flask.request.form:
        raise http_error.BadRequest()

    if 'Authorization' in flask.request.headers:
        # ticket verification
        parts = flask.request.headers['Authorization'].split()
        if parts[0].lower() == 'bearer':
            token = parse_token(parts[1])
            return json.dumps(token), {'Content-Type': 'application/json'}
        raise http_error.Unauthorized("Invalid authorization header")

    raise http_error.BadRequest()
