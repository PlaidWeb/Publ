#!/usr/bin/env python3
# Main Publ application

import os.path
import markdown

import config
import publ
import logging

from flask import Flask,redirect,render_template,send_from_directory,url_for

app = Flask(__name__,
    static_folder=config.static_directory,
    static_path=config.static_path,
    template_folder=config.template_directory)

def map_template(path, template):
    path = os.path.normpath(path)
    app.logger.debug('looking for template %s in directory %s', template, path)
    while True:
        for extension in ['', '.html', '.xml', '.json']:
            candidate = os.path.join(path, template + extension)
            app.logger.debug("checking candidate %s" % candidate)
            if os.path.isfile(os.path.join(config.template_directory, candidate)):
                app.logger.debug("found %s", candidate)
                return candidate
        parent = os.path.dirname(path)
        if parent == path:
            app.logger.warning("Couldn't find template %s for path %s", template_type, orig_path)
            return None
        path = parent

@app.route('/')
@app.route('/<path:category>/')
@app.route('/<template>')
@app.route('/<path:category>/<template>')
def render_category(category='', template='index'):
    tmpl = map_template(category, template)
    return 'render template {} for category {}'.format(tmpl, category)

@app.route('/<int:entry_id>')
@app.route('/<int:entry_id>-<slug_text>')
@app.route('/<path:category>/<int:entry_id>')
@app.route('/<path:category>/<int:entry_id>-<slug_text>')
def render_entry(entry_id, slug_text='', category=''):
    # check if it's a valid entry
    idx_entry = publ.model.Entry.get_or_none(publ.model.Entry.id == entry_id)
    if not idx_entry:
        app.logger.info("Attempted to retrieve nonexistent entry %d", entry_id)
        return render_template(map_template(category, '404')), 404

    if idx_entry.category != category or idx_entry.slug_text != slug_text:
        return redirect(url_for('render_entry',
            entry_id=entry_id,
            category=idx_entry.category,
            slug_text=idx_entry.slug_text))

    tmpl = map_template(category, 'entry')
    entry_data = publ.entry.Entry(idx_entry.file_path)
    if entry_data.markdown:
        entry_data.body = entry_data.body and markdown.markdown(entry_data.body)
        entry_data.more = entry_data.more and markdown.markdown(entry_data.more)
    return render_template(tmpl, entry=entry_data)

logging.info("Setting up")
publ.model.create_tables()
publ.index.scan_index(config.content_directory)

if __name__ == "__main__":
    app.run(debug=True)
