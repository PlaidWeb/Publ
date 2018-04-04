#!/usr/bin/env python3
# Main Publ application

import os
import markdown

import config
import publ
import logging

import flask

# logging.basicConfig(level=logging.DEBUG)

logging.info("Setting up")

app = flask.Flask(__name__,
    static_folder=config.static_directory,
    static_path=config.static_path,
    template_folder=config.template_directory)
app.config['SERVER_NAME'] = config.server_name

publ.setup(app)

def scan_index():
    publ.model.create_tables()
    publ.index.scan_index(config.content_directory)

scan_index()

if __name__ == "__main__":
    app.run()

