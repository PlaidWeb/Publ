# app.py
# Main Publ application

import config
import os.path
from flask import Flask,redirect,render_template

static_root_dir = os.path.join(os.getcwd(), 'public')
app = Flask(__name__,
    static_folder=config.static_directory,
    static_path=config.static_path,
    template_folder=config.template_directory)

def map_template(path, template_type):
    path = os.path.normpath(path)
    while len(path) > 0:
        candidate = os.path.join(path, template_type + '.html')
        app.logger.debug("checking candidate %s" % candidate)
        if os.path.isfile(os.path.join(config.template_directory, candidate)):
            return candidate
        path = os.path.dirname(path)

@app.route('/')
def main_page():
    return render_index('')

@app.route('/<path:path>/')
def render_index(path):
    tmpl = map_template(path, 'index')
    return 'render index template %s' % tmpl

@app.route('/<path:path>/<entry>')
def render_entry(path, entry):
    fullpath = os.path.normpath(os.path.join(path, entry))
    filepath = os.path.join(config.entries_directory, fullpath)
    if os.path.isdir(filepath):
        return render_index(fullpath)

    if os.path.isfile(filepath):
        tmpl = map_template(path, 'entry')
        return 'render file %s with template %s' % (os.path.join(path, entry), tmpl)

    # TODO check legacy path mappings

    return render_template(os.path.join('404.html'), path=path, entry=entry), 404

@app.route('/<path:path>/feed')
def render_feed(path):
    tmpl = map_template(path, 'feed')
    return 'render feed template %s' % tmpl

if __name__ == "__main__":
    app.run(debug=True)
