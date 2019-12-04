""" IndieAuth token endpoint """

import logging
import typing

import flask
import itsdangerous
import requests
import werkzeug.exceptions as http_error
from authl.handlers import indieauth

from . import config, utils
from .caching import cache

LOGGER = logging.getLogger(__name__)


def signer():
    """ Gets the signer/validator for the tokens """
    return itsdangerous.URLSafeTimedSerializer(flask.current_app.secret_key)


def token_endpoint():
    """ Public endpoint for token generation

    This implements the Token Request protocol described at
    https://github.com/sknebel/AutoAuth/blob/master/AutoAuth.md#token-request
    """

    @cache.memoize()
    def get_remote_endpoint(id_url):
        return indieauth.find_endpoint(id_url)

    try:
        post = flask.request.form
        if post['grant_type'] != 'authorization_code':
            raise http_error.BadRequest("Unsupported grant type")

        data = {k: v for k, v in post.items() if k in (
            'client_id',
            'code',
            'me',
            'realm',
            'redirect_uri',
            'root_url',
            'scope',
        )}

        LOGGER.debug("Verification data: %s", data)

        endpoint = get_remote_endpoint(post['me'])
        LOGGER.debug("Endpoint: %s", endpoint)

        validation = requests.post(endpoint, data=data, headers={
            'accept': 'application/json'
        })

        if validation.status_code != 200:
            LOGGER.error("Endpoint returned %d: %s",
                         validation.status_code,
                         validation.text)
            raise http_error.BadRequest(
                "Authorization endpoint returned error " + str(validation.status_code))

        response = validation.json()

        if 'me' in response:
            id_url = indieauth.verify_id(post['me'], response['me'])
            if not id_url:
                raise http_error.BadRequest("Mismatched 'me' URL")
        else:
            id_url = post['me']

        identity = {
            'me': id_url,
            'scope': response.get('scope', post.get('scope'))
        }

        token = signer().dumps({k: v for k, v in identity.items() if v})

        return flask.jsonify({
            'access_token': token,
            'expires_in': config.max_token_age,
            'scope': response.get('scope', 'read'),
            'token_type': 'bearer',
        })
    except KeyError as key:
        raise http_error.BadRequest("Missing value: " + str(key))


def parse_token(token: str) -> typing.Dict[str, str]:
    """ Parse a bearer token to get the stored data """
    try:
        return signer().loads(token, max_age=config.max_token_age)
    except itsdangerous.BadData as error:
        LOGGER.error("Got token parse error: %s", error)
        flask.g.user = None
        flask.g.token_error = error.message
        raise http_error.Unauthorized(error.message)


def inject_auth_headers(response):
    """ If the request triggered a need to authenticate, add the appropriate
    headers. """

    if flask.g.get('needs_token'):
        header = 'Bearer, realm="posts", scope="read"'
        if 'token_error' in flask.g:
            header += ', error="invalid_token", error_description="{msg}"'.format(
                msg=flask.g.token_error)
        response.headers.add('WWW-Authenticate', header)
        response.headers.add('Link', '<{endpoint}>; rel="token_endpoint"'.format(
            endpoint=utils.secure_link('token', _external=True)))

    return response


def request(user):
    """ Called whenever an authenticated access fails; marks authentication
    as being upgradeable. """
    if not user:
        flask.g.needs_token = True
    return user
