from . import rendering, model, index
import arrow
import flask

model = model
index = index

def setup(app):
    for route in [
    '/',
    '/<path:category>/',
    '/<template>',
    '/<path:category>/<template>',
    ]:
        app.add_url_rule(route, 'category', rendering.render_category)

    for route in [
    '/<int:entry_id>',
    '/<int:entry_id>-<slug_text>',
    '/<path:category>/<int:entry_id>',
    '/<path:category>/<int:entry_id>-<slug_text>',
    ]:
        app.add_url_rule(route, 'entry', rendering.render_entry)

    app.jinja_env.globals.update(get_view=view.get_view, arrow=arrow, static=rendering.static_url)
