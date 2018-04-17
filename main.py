#!/usr/bin/env python3
""" Main Publ application """

import os
import logging
import logging.handlers

import flask

import config
import publ


if not os.path.exists(config.log_directory):
    os.mkdir(config.log_directory)
if not os.path.exists(config.data_directory):
    os.mkdir(config.data_directory)

if os.path.isfile('logging.conf'):
    logging.config.fileConfig('logging.conf')
else:
    logging.basicConfig(level=logging.INFO,
                        handlers=[
                            logging.handlers.TimedRotatingFileHandler(
                                'tmp/publ.log'),
                            logging.StreamHandler()
                        ])

logging.info("Setting up")


def startup(name):
    """ Build the Flask application. Wrapped in a function to keep pylint happy. """
    # TODO https://github.com/fluffy-critter/Publ/issues/20
    # move to app.config.from_object
    flask_app = flask.Flask(name,
                            static_folder=config.static_directory,
                            static_path=config.static_path,
                            template_folder=config.template_directory)  # pylint: disable=invalid-name
    flask_app.config['SERVER_NAME'] = config.server_name
    publ.setup(flask_app)
    return flask_app

app = startup(__name__)  # pylint: disable=invalid-name


@app.after_request
def set_cache_expiry(req):
    """ Set the cache control headers """
    req.headers['Cache-Control'] = 'public, max-age=300'
    return req


if __name__ == "__main__":
    app.run(port=os.environ.get('PORT', 5000))
