""" Smoke test site runner """
# pylint:disable=invalid-name

import logging
import os

import authl.flask
import flask

import publ
import publ.image

APP_PATH = os.path.dirname(os.path.abspath(__file__))

logging.basicConfig(level=logging.DEBUG)

config = {
    'database_config': {
        'provider': 'sqlite',
        'filename': os.path.join(APP_PATH, '..', 'index.db')
    },
    'content_folder': os.path.join(APP_PATH, 'content'),
    'template_folder': os.path.join(APP_PATH, 'templates'),
    'static_folder': os.path.join(APP_PATH, 'static'),
    'cache': {
        'CACHE_TYPE': os.environ['TEST_CACHING'],
        'CACHE_DEFAULT_TIMEOUT': 600,
        'CACHE_THRESHOLD': 20
    } if os.environ.get('TEST_CACHING') else {
        'CACHE_NO_NULL_WARNING': True
    },
    'auth': {
        'TEST_ENABLED': True,

        'INDIEAUTH_CLIENT_ID': authl.flask.client_id,
        'INDIELOGIN_CLIENT_ID': authl.flask.client_id,

        'FEDIVERSE_NAME': 'Publ test suite',

        'TWITTER_CLIENT_KEY': os.environ.get('TWITTER_CLIENT_KEY'),
        'TWITTER_CLIENT_SECRET': os.environ.get('TWITTER_CLIENT_SECRET'),

        'EMAIL_SENDMAIL': print,
        'EMAIL_FROM': 'nobody@example.com',
        'EMAIL_SUBJECT': 'Log in to authl test',
        'EMAIL_CHECK_MESSAGE': 'Use the link printed to the test console',
    },
    'user_list': 'users.cfg',
}

app = publ.Publ(__name__, config)
app.secret_key = "We are insecure"


@app.route('/favicon.<ext>')
def favicon(ext):
    """ render a favicon """
    logo = publ.image.get_image('images/rawr.jpg', 'tests/content')
    img, _ = logo.get_rendition(format=ext, width=128, height=128, resize='fill')
    return flask.redirect(img)
