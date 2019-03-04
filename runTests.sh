#!/bin/sh

pipenv install --dev || exit 1

cd $(dirname $0)/tests
FLASK_DEBUG=1 pipenv run python main.py
