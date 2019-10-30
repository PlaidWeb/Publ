""" IndieAuth token endpoint """

import logging

import flask
import itsdangerous
import requests
import werkzeug.exceptions as http_error
from authl.handlers import indieauth

from . import config
from .caching import cache

LOGGER = logging.getLogger(__name__)


def signer():
    """ Gets the signer/validator for the tokens """
    return itsdangerous.URLSafeTimedSerializer(config.secret_key)


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

        request = requests.post(endpoint, data=data, headers={
            'accept': 'application/json'
        })

        if request.status_code != 200:
            LOGGER.error("Endpoint returned %d: %s", request.status_code, request.text)
            raise http_error.BadRequest(
                "Authorization endpoint returned error " + str(request.status_code))

        response = request.json()

        token = signer().dumps({k: v for k, v in response.items() if k in (
            'me',
            'scope',
        )})

        return flask.jsonify({
            'access_token': token,
            'expires_in': config.max_token_age,
            'scope': response.get('scope', 'read'),
            'token_type': 'bearer',
        })
    except KeyError as key:
        raise http_error.BadRequest("Missing value: " + str(key))


def parse_token(token: str) -> str:
    """ Parse a bearer token to get the stored data """
    return signer().loads(token, max_age=config.max_token_age)
