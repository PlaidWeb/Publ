#!/usr/bin/env python3
# Main Publ application

import os

import config
import publ
import logging, logging.handlers

import flask

if not os.path.exists(config.log_directory):
    os.mkdir(config.log_directory)
if not os.path.exists(config.data_directory):
    os.mkdir(config.data_directory)

if os.path.isfile('logging.conf'):
    logging.config.fileConfig('logging.conf')
else:
    logging.basicConfig(level=logging.INFO,
        handlers=[
            logging.handlers.TimedRotatingFileHandler('tmp/publ.log'),
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
    r.headers["Expires"] = "5"
    r.headers['Cache-Control'] = 'public, max-age=5'
    return r


publ.setup(app)

def scan_index():
    publ.model.create_tables()
    publ.index.scan_index(config.content_directory)
    publ.index.background_scan(config.content_directory)

scan_index()

if __name__ == "__main__":
    app.run(port=os.environ.get('PORT',5000))

