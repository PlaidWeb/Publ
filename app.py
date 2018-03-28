# app.py
# Main Publ application

import config
import os.path
from flask import Flask

static_root_dir = os.path.join(os.getcwd(), 'public')
app = Flask(__name__, static_folder=static_root_dir, static_path='/')

def map_template(path, template_type):
    path = os.path.join(config.template_directory, os.path.normpath(path))
    while len(path) > 0:
        candidate = os.path.join(path, template_type + '.html')
        app.logger.debug("checking candidate %s" % candidate)
        if os.path.isfile(candidate):
            return candidate
        path = os.path.dirname(path)

@app.route('/<path:path>/')
def render_index(path):
    tmpl = map_template(path, 'index')
    return 'render index template %s' % tmpl

@app.route('/<path:path>/<entry>')
def render_entry(path, entry):
    tmpl = map_template(path, 'entry')
    return 'render file %s with template %s' % (os.path.join(path, entry), tmpl)

@app.route('/<path:path>/feed')
def render_feed(path):
    tmpl = map_template(path, 'feed')
    return 'render feed template %s' % tmpl

if __name__ == "__main__":
    app.run(debug=True)
