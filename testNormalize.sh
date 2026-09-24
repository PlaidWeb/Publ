#!/bin/sh
# specific test of the normalize command

cd "$(dirname "$0")"
poetry install

export FLASK_APP=test_app.py

poetry run flask publ reindex
poetry run flask publ normalize -rv -f "_{type}-{title}" \
    -F '' "{date}-{sid} {title}" \
    -F 'collide' "{title}" \
    -g nonorm \
    normalize

