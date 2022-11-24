""" IndieAuth token endpoint """

import functools
import json
import logging
import time
import typing
import urllib.parse
from typing import Optional

import arrow
import flask
import itsdangerous
import requests
import werkzeug.exceptions as http_error
from pony import orm

from . import model, utils
from .config import config

LOGGER = logging.getLogger(__name__)


def signer(context: str):
    """ Gets the signer/validator for the tokens """
    from .flask_wrapper import current_app
    return itsdangerous.URLSafeSerializer(str(current_app.secret_key) + context)


def get_token(id_url: str, lifetime: int, scope: Optional[str] = None, context: str = '') -> str:
    """ Gets a signed token for the given identity"""
    token = {'me': utils.canonicize_url(id_url)}
    if scope:
        token['scope'] = scope

    return signer(context).dumps((token, int(time.time() + lifetime)))


def parse_token(token: str, context: str = '') -> typing.Dict[str, str]:
    """ Parse a bearer token to get the stored data """
    try:
        ident, expires = signer(context).loads(token)
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
                     scope: Optional[str] = None):
    """ Initiate the TicketAuth flow """
    from .flask_wrapper import current_app

    def _submit():
        ticket = get_token(subject, config.ticket_lifetime, scope, context='ticket')

        req = requests.post(endpoint, data={
            'ticket': ticket,
            'resource': resource,
            'subject': subject
        })
        LOGGER.info("Auth ticket sent to %s for %s: %d %s",
                    endpoint, subject, req.status_code, req.text)

    # Use the indexer's threadpool to issue the ticket in the background
    current_app.indexer.submit(_submit)


@orm.db_session()
def log_grant(identity: str):
    """ Update the user table with the granted token """
    import authl.handlers.indieauth

    values = {
        'last_token': arrow.utcnow().datetime,
    }

    profile = authl.handlers.indieauth.get_profile(identity)
    if profile:
        values['profile'] = profile

    record = model.KnownUser.get(user=identity)
    if record:
        record.set(**values)
    else:
        record = model.KnownUser(user=identity,
                                 **values,
                                 last_seen=arrow.utcnow().datetime)


def redeem_grant(grant_type: str, auth_token: str):
    """ Redeem a grant from a provided redemption ticket """
    grant = parse_token(auth_token, grant_type)
    LOGGER.info("Redeeming %s for %s; scopes=%s", grant_type, grant['me'],
                grant.get('scope'))

    scope = grant.get('scope', '')

    token = get_token(grant['me'], config.token_lifetime, scope)

    response = {
        'access_token': token,
        'token_type': 'Bearer',
        'me': grant['me'],
        'expires_in': config.token_lifetime,
        'refresh_token': get_token(grant['me'],
                                   config.refresh_token_lifetime,
                                   scope,
                                   context='refresh_token')
    }
    if scope:
        response['scope'] = scope

    log_grant(grant['me'])

    return json.dumps(response), {'Content-Type': 'application/json'}


@functools.lru_cache()
def get_ticket_endpoint(me_url: str):
    """ Get the IndieAuth Ticket Auth endpoint and the canonical identity URL """
    LOGGER.debug("get_ticket_endpoint %s", me_url)
    import authl.handlers.indieauth
    from bs4 import BeautifulSoup

    req = authl.utils.request_url(me_url)
    content = BeautifulSoup(req.text, 'html.parser')

    if req.links and 'canonical' in req.links:
        canonical_url = req.links['canonical']['url']
    else:
        link = content.find('link', rel='canonical')
        if link:
            canonical_url = urllib.parse.urljoin(me_url, link.get('href'))
        else:
            canonical_url = me_url

    if utils.canonicize_url(canonical_url) != utils.canonicize_url(me_url):
        # We have a rel="canonical" which mismatches the provided identity URL
        LOGGER.debug("%s -> canonical=%s", me_url, canonical_url)
        endpoint, me_url = authl.handlers.indieauth.find_endpoint(canonical_url,
                                                                  rel='ticket_endpoint')
    else:
        # Use our fetch to seed Authl's endpoint fetch and get that instead
        endpoints, me_url = authl.handlers.indieauth.find_endpoints(me_url,
                                                                    req.links, content)
        endpoint = endpoints.get('ticket_endpoint')

    LOGGER.debug("%s %s", me_url, endpoint)
    return endpoint, me_url


def ticket_request(me_url: str, scope: str):
    """ Initiate a ticket request """

    try:
        endpoint, me_url = get_ticket_endpoint(utils.canonicize_url(me_url))
    except RuntimeError:
        endpoint = None
    if not endpoint:
        raise http_error.BadRequest("Could not get ticket endpoint")
    LOGGER.info("endpoint: %s", endpoint)
    send_auth_ticket(me_url, flask.request.url_root, endpoint, scope)
    return "Ticket sent", 202


def parse_authorization_header(header):
    """ Parse an Authorization: header from an HTTP request into token """
    parts = header.split()
    if len(parts) < 2:
        raise http_error.BadRequest("Malformed authorization header")

    if parts[0].lower() == 'bearer':
        token = parse_token(parts[1])
        return token

    raise http_error.BadRequest(f"Unknown authorization type '{parts[0]}'")


def indieauth_endpoint():
    """ IndieAuth token endpoint """

    if 'grant_type' in flask.request.form:
        # token grant
        if flask.request.form['grant_type'] == 'ticket':
            # TicketAuth
            if 'ticket' not in flask.request.form:
                raise http_error.BadRequest("Missing ticket")
            return redeem_grant('ticket', flask.request.form['ticket'])

        if flask.request.form['grant_type'] == 'refresh_token':
            # Refresh token redemption
            if 'refresh_token' not in flask.request.form:
                raise http_error.BadRequest("Missing refresh_token")
            return redeem_grant('refresh_token', flask.request.form['refresh_token'])

        raise http_error.BadRequest("Unknown grant type")

    if 'action' in flask.request.form:
        # provisional ticket request flow, per https://github.com/indieweb/indieauth/issues/87
        if flask.request.form['action'] == 'ticket' and 'subject' in flask.request.form:
            return ticket_request(flask.request.form['subject'],
                                  flask.request.form.get('scope', ''))

        raise http_error.BadRequest()

    if 'Authorization' in flask.request.headers:
        # ticket verification
        token = parse_authorization_header(flask.request.headers['Authorization'])
        return json.dumps(token), {'Content-Type': 'application/json'}

    if 'me' in flask.request.args:
        # ad-hoc ticket request
        return ticket_request(flask.request.args['me'],
                              flask.request.args.get('scope', ''))

    raise http_error.BadRequest()
