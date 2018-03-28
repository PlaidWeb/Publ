#!/usr/bin/env python3
# Main Publ application

import os.path
import markdown

import config
import entry

from flask import Flask,redirect,render_template,send_from_directory

static_root_dir = os.path.join(os.getcwd(), 'public')
app = Flask(__name__,
    static_folder=config.static_directory,
    static_path=config.static_path,
    template_folder=config.template_directory)

def map_template(path, template_type):
    orig_path = path
    path = os.path.normpath(path)
    while True:
        candidate = os.path.join(path, template_type + '.html')
        app.logger.debug("checking candidate %s" % candidate)
        if os.path.isfile(os.path.join(config.template_directory, candidate)):
            app.logger.debug("found %s" % candidate)
            return candidate
        parent = os.path.dirname(path)
        if parent == path:
            app.logger.warning("Couldn't find template %s for path %s" % (template_type, orig_path))
            return None
        path = parent

def map_entry_file(path):
    entry_file = path + ".md"
    app.logger.debug("trying " + entry_file)
    if os.path.isfile(entry_file):
        return entry_file
    app.logger.debug("not found")
    return None

@app.route('/')
def main_page():
    return render_index('')

@app.route('/<path:path>/')
def render_index(path):
    tmpl = map_template(path, 'index')
    return 'render index template %s' % tmpl

@app.route('/<path:path>/feed')
def render_feed(path):
    tmpl = map_template(path, 'feed')
    return 'render feed template %s' % tmpl

@app.route('/<item>')
def root_directory(item):
    return render_entry('', item)

@app.route('/<path:path>/<item>')
def render_entry(path, item):
    fullpath = os.path.normpath(os.path.join(path, item))
    filepath = os.path.join(config.entries_directory, fullpath)
    if os.path.isdir(filepath):
        return render_index(fullpath)

    entry_file = map_entry_file(filepath)
    app.logger.debug("got entry file %s -> %s" % (filepath, entry_file))
    if entry_file:
        tmpl = map_template(path, 'entry')
        app.logger.debug("rendering %s with %s" % (entry_file, tmpl))
        return render_template(tmpl, entry=entry.parse(entry_file))

    # TODO: check for legacy URL mapping

    # check for static content
    if os.path.isfile(os.path.join(config.static_directory, fullpath)):
        app.logger.debug("sending static content for %s" % fullpath)
        return send_from_directory(config.static_directory, fullpath)

    # entry not found
    return render_template(os.path.join('404.html'), path=os.path.join(path, item)), 404

if __name__ == "__main__":
    app.run(debug=True)
