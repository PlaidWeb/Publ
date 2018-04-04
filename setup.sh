#!/bin/sh

if ! which pipenv > /dev/null ; then
    echo "Couldn't find pipenv"
    exit 1
fi

if [ ! -f config.py ] ; then
    echo "Please copy config.py.dist to config.py and edit the settings accordingly (if appropriate)"
    exit 1
fi

echo "Configuring environment..."

pipenv install

echo "Updating data..."
#mkdir -p data
#pipenv run python -c "import db; db.create_tables()" || exit $?

# Restart Passenger (at least per Dreamhost's config)
mkdir -p tmp data
touch tmp/restart.txt

echo "Setup complete."
