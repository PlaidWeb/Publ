import os
import logging

import flask

import publ
import publ.image

APP_PATH = os.path.dirname(os.path.abspath(__file__))

logging.basicConfig(level=logging.DEBUG)

config = {
    # Leave this off to do an in-memory database
    'database_config': {
        'provider': 'sqlite',
        'filename': os.path.join(APP_PATH, 'index.db')
    },
    'content_folder': 'tests/content',
    'template_folder': 'tests/templates',
    'static_folder': 'tests/static',
    'cache': {
        'CACHE_TYPE': 'simple',
        'CACHE_DEFAULT_TIMEOUT': 600,
        'CACHE_THRESHOLD': 20
    } if os.environ.get('TEST_CACHING') else {
        'CACHE_NO_NULL_WARNING': True
    },
    'auth': {
        'TEST_ENABLED': True
    },
    'user_list': 'tests/users.cfg'
}

app = publ.Publ(__name__, config)


@app.route('/favicon.ico')
def favicon():
    logo = publ.image.get_image('images/rawr.jpg', ['tests/content'])
    img, _ = logo.get_rendition(format='ico')
    return flask.redirect(img)


if __name__ == "__main__":
    app.run(port=os.environ.get('PORT', 5000))
