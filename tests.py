import os
import logging

import flask

import publ
import publ.image

APP_PATH = os.path.dirname(os.path.abspath(__file__))

logging.basicConfig(level=logging.INFO)

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
        'CACHE_NO_NULL_WARNING': True
    },
}

app = publ.publ(__name__, config)


@app.route('/favicon.ico')
def favicon():
    logo = publ.image.get_image('rawr.jpg', ['tests/content'])
    img, _ = logo.get_rendition(format='ico')
    return flask.redirect(img)

if __name__ == "__main__":
    app.run(port=os.environ.get('PORT', 5000))
