#!/bin/sh

if [ "$1" != "fast" ] ; then
    pipenv install --dev || exit 1
fi

FLASK_DEBUG=1 FLASK_ENV=development pipenv run python tests.py
