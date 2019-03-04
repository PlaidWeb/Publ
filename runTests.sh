#!/bin/sh

pipenv install --dev || exit 1

FLASK_DEBUG=1 FLASK_ENV=development pipenv run python tests.py
