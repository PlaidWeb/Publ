""" IndieAuth token endpoint """

import logging
import time
import typing

import flask
import itsdangerous
import werkzeug.exceptions as http_error

LOGGER = logging.getLogger(__name__)


def signer():
    """ Gets the signer/validator for the tokens """
    return itsdangerous.URLSafeSerializer(flask.current_app.secret_key)


def get_token(id_url: str, lifetime: int, scope: str = None) -> str:
    """ Gets a signed token for the given identity and scope """
    token = {
        'me': id_url
    }
    if scope is not None:
        token['scope'] = scope

    return signer().dumps((token, int(time.time() + lifetime)))


def parse_token(token: str) -> typing.Dict[str, str]:
    """ Parse a bearer token to get the stored data """
    try:
        ident, expires = signer().loads(token)
    except itsdangerous.BadData as error:
        LOGGER.error("Got token parse error: %s", error)
        flask.g.token_error = error.message
        raise http_error.Unauthorized(error.message)

    if expires < time.time():
        LOGGER.info("Got expired token for %s", ident['me'])
        flask.g.token_error = "Token expired"
        raise http_error.Unauthorized("Token expired")

    return ident


def request(user):
    """ Called whenever an authenticated access fails; marks authentication
    as being upgradeable.

    This was added for the purpose of supporting AutoAuth, but with the death
    of that initiative the token_endpoint stuff was removed. This functionality
    thus stays around as a just-in-case for later.
    """

    if not user:
        flask.g.needs_auth = True
