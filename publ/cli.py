""" CLI utilities for Publ """

import itertools
import time

import click
from flask.cli import AppGroup, with_appcontext

from .config import config

publ_cli = AppGroup('publ', short_help="Publ-specific commands")  # pylint:disable=invalid-name


@publ_cli.command('reindex', short_help="Reindex the content store")
@click.option('--quietly', '-q', 'quietly', is_flag=True, help="Quietly")
@click.option('--fresh', '-f', 'fresh', is_flag=True, help="Start with a fresh database")
@with_appcontext
def reindex_command(quietly, fresh):
    """ Command for reindexing the index """
    from . import index, model

    if fresh:
        model.reset()

    spinner = itertools.cycle('|/-\\')

    index.scan_index(config.content_folder, False)
    while index.in_progress():
        if not quietly:
            qlen = index.queue_size() or ''
            print("\rIndexing... %s %s        " % (next(spinner), qlen), end='', flush=True)
        time.sleep(0.1)
    if not quietly:
        print("Done")


@publ_cli.command('token', short_help="Generate a bearer token")
@click.argument('identity')
@click.option('--scope', '-s', help="The token's permission scope")
@click.option('--lifetime', '-l', help="The token's lifetime (in seconds)")
@with_appcontext
def token_command(identity, scope, lifetime=3600):
    """ Command to retrieve a bearer token """
    from . import tokens
    print(tokens.get_token(identity, int(lifetime), scope))


def setup(app):
    """ Register the CLI commands with the command parser """
    app.cli.add_command(publ_cli)
