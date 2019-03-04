#!/bin/sh

pipenv install --dev || exit 1

FLASK_DEBUG=1 pipenv run python tests.py
