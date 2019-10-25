#!/bin/sh

if [ "$1" != "fast" ] ; then
    pipenv install --dev || exit 1
fi

FLASK_DEBUG=1 FLASK_ENV=development FLASK_APP=tests.py pipenv run flask run
