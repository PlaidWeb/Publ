#!/usr/bin/env python3
# Main Publ application

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

# TODO https://github.com/fluffy-critter/Publ/issues/20
# move to app.config.from_object
app = flask.Flask(__name__,
                  static_folder=config.static_directory,
                  static_path=config.static_path,
                  template_folder=config.template_directory)
app.config['SERVER_NAME'] = config.server_name


@app.after_request
def set_cache_expiry(r):
    r.headers['Cache-Control'] = 'public, max-age=300'
    return r

publ.setup(app)

if __name__ == "__main__":
    app.run(port=os.environ.get('PORT', 5000))
