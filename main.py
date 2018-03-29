#!/usr/bin/env python3
# Main Publ application

import os.path
import markdown

import config
import item

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
        # TODO map html, xml, or whatever, and provide an appropriate content-type too
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

def map_content_file(path):
    # TODO this goes away, since we'll be looking up by id in the data store and
    # getting the appropriately-formatted content from there
    content_file = path + ".md"
    app.logger.debug("  trying " + content_file)
    if os.path.isfile(content_file):
        return content_file
    app.logger.debug("not found")
    return None

@app.route('/')
def main_page():
    return render_index('')

@app.route('/<path:path>/')
def render_index(path):
    tmpl = map_template(path, 'index')
    return 'render index template %s for category %s' % (tmpl, path)

@app.route('/<entry>')
def root_directory(entry):
    return render_content('', entry)

@app.route('/<path:path>/<entry>')
def render_content(path, entry):
    # TODO entry will be a thing that gets parsed:
    #   <int:id> redirects to item's canonical URL
    #   <int:id>-slug renders the content OR redirects to the canonical URL if it doesn't match
    #   <name> renders the path's template, or returns the static content or whatever
    fullpath = os.path.normpath(os.path.join(path, entry))
    filepath = os.path.join(config.content_directory, fullpath)
    if os.path.isdir(filepath):
        return render_index(fullpath)

    content_file = map_content_file(filepath)
    app.logger.debug("got content file %s -> %s" % (filepath, content_file))
    if content_file:
        tmpl = map_template(path, 'entry')
        app.logger.debug("rendering %s with %s" % (content_file, tmpl))
        return render_template(tmpl, entry=item.parse(content_file))

    # maybe it's a template?
    template_file = map_template(path, entry)
    if template_file:
        return 'render template %s for category %s' % (template_file, path)

    # TODO: check for legacy URL mapping

    # content not found
    return render_template(os.path.join('404.html'), path=os.path.join(path, entry)), 404

if __name__ == "__main__":
    app.run(debug=True)
