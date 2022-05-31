""" Smoke test site runner """
# pylint:disable=invalid-name

import logging
import os

try:
    import authl.flask
except ImportError:
    authl = None

try:
    import whoosh
except ImportError:
    whoosh = None

import flask

import publ
import publ.image

APP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tests')

logging.basicConfig(level=logging.DEBUG if 'FLASK_DEBUG' in os.environ else logging.WARNING)

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
        'CACHE_TYPE': 'NullCache',
        'CACHE_NO_NULL_WARNING': True
    },
    'auth': {
        'TEST_ENABLED': True,

        'INDIEAUTH_CLIENT_ID': authl.flask.client_id if authl else None,
        'INDIELOGIN_CLIENT_ID': authl.flask.client_id if authl else None,

        'FEDIVERSE_NAME': 'Publ test suite',

        'TWITTER_CLIENT_KEY': os.environ.get('TWITTER_CLIENT_KEY'),
        'TWITTER_CLIENT_SECRET': os.environ.get('TWITTER_CLIENT_SECRET'),

        'EMAIL_SENDMAIL': print,
        'EMAIL_FROM': 'nobody@example.com',
        'EMAIL_SUBJECT': 'Log in to authl test',
        'EMAIL_CHECK_MESSAGE': 'Use the link printed to the test console',
    } if authl else {},
    'user_list': os.path.join(APP_PATH, 'users.cfg'),
    'layout': {
        'max_width': 768,
    },
    'search_index': '_index' if whoosh else None,
    'index_enable_watchdog': False,
}

app = publ.Publ(__name__, config)
app.secret_key = "We are insecure"


@app.route('/favicon.<ext>')
def favicon(ext):
    """ render a favicon """
    logo = publ.image.get_image('images/rawr.jpg', 'tests/content')
    img, _ = logo.get_rendition(format=ext, width=128, height=128, resize='fill')
    return flask.redirect(img)


@app.path_alias_regex(r'(.*)/date/([0-9]+)')
def date_view(match):
    """ Simple test of regex path aliases, maps e.g. /foo/date/2020 to /foo/?date=2020 """
    return flask.url_for('category', category=match.group(1),
                         date=match.group(2)), True
