#!/bin/sh
# Simple interactive smoke test runner.
#
# Run with a parameter of 'fast' to skip the package install.
#
# Some useful environment variables:
#
# TWITTER_CLIENT_KEY, TWITTER_CLIENT_SECRET: used to test Twitter login;
# note that Twitter doesn't support callbacks on `localhost` but you can
# use `lvh.me` instead (e.g. http://lvh.me:5000/)
#
# FLASK_RUN_PORT: set an alternate bind port for the test server
#
# TEST_CACHING: set to a Flask-Caching module name, e.g. 'simple' or 'memcached'

if [ "$1" != "fast" ] ; then
    poetry install || exit 1
fi

FLASK_DEBUG=1 FLASK_ENV=development FLASK_APP=test_app.py poetry run flask run
