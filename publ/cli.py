""" CLI utilities for Publ """
# pylint:disable=too-many-arguments

import itertools
import logging
import os.path
import re
import time

import arrow
import click
import slugify
from flask.cli import AppGroup, with_appcontext
from pony import orm

from . import queries
from .config import config

LOGGER = logging.getLogger(__name__)

publ_cli = AppGroup('publ', short_help="Publ-specific commands")  # pylint:disable=invalid-name


@publ_cli.command('reindex', short_help="Reindex the content store")
@click.option('--quietly', '-q', 'quietly', is_flag=True, help="Quietly")
@click.option('--fresh', '-f', 'fresh', is_flag=True, help="Start with a fresh database")
@with_appcontext
def reindex_command(quietly, fresh):
    """ Forces a reindex of the content store.

    This is particularly useful to ensure that all content has been indexed
    before performing another action, such as sending out notifications.
    """
    from . import index, model

    if fresh:
        model.reset()

    spinner = itertools.cycle('|/-\\')

    index.scan_index(config.content_folder, False)
    while index.in_progress():
        if not quietly:
            qlen = index.queue_size() or ''
            print(f"\rIndexing... {next(spinner)} {qlen}        ", end='', flush=True)
        time.sleep(0.1)
    if not quietly:
        print("Done")


@publ_cli.command('token', short_help="Generate a bearer token")
@click.argument('identity')
@click.option('--scope', '-s', help="The token's permission scope")
@click.option('--lifetime', '-l', help="The token's lifetime (in seconds)", default=3600)
@with_appcontext
def token_command(identity, scope, lifetime):
    """ Generates a bearer token for use with external applications. """
    from . import tokens
    print(tokens.get_token(identity, int(lifetime), scope))


@publ_cli.command('normalize', short_help="Normalize entry filenames")
@click.argument('category', nargs=-1)
@click.option('--recurse', '-r', 'recurse', is_flag=True,
              help="Include subdirectories")
@click.option('--all', '-a', 'all_entries', is_flag=True,
              help="Apply to all entries, not just reachable ones")
@click.option('--dry-run', '-n', 'dry_run', is_flag=True,
              help="Show, but don't apply, changes")
@click.option('--format', '-f', 'format_str',
              help="Filename format to use",
              default="{date} {sid} {title}")
@click.option('--verbose', '-v', 'verbose', is_flag=True,
              help="Show detailed actions")
@with_appcontext
@orm.db_session
def normalize_command(category, recurse, dry_run, format_str, verbose, all_entries):
    """ Normalizes the filenames of content files based on a standardized format.

    This will only normalize entries which are already in the content index.

    If no categories are specified, it defaults to the root category. To include
    the root category in a list of other categories, use an empty string parameter,
    e.g.:

        flask publ normalize '' blog

    Available tokens for --format/-f:

        {date}    The entry's publish date, in YYYYMMDD format

        {time}    The entry's publish time, in HHMMSS format

        {id}      The entry's ID

        {status}  The entry's publish status

        {sid}     If the entry is reachable, the ID, otherwise the status

        {title}   The entry's title, normalized to filename-safe characters

        {slug}    The entry's slug text

        {type}    The entry's type
    """
    # pylint:disable=too-many-locals

    from .model import PublishStatus

    entries = queries.build_query({
        'category': category or '',
        'recurse': recurse,
        '_future': True,
        '_all': all_entries,
    })

    fname_slugify = slugify.UniqueSlugify(max_length=100, safe_chars='-.', separator=' ')

    for entry in entries:
        path = os.path.dirname(entry.file_path)
        basename, ext = os.path.splitext(os.path.basename(entry.file_path))

        status = PublishStatus(entry.status)

        eid = entry.id
        if status == PublishStatus.DRAFT:
            # Draft entries don't get a stable entry ID
            eid = status.name

        sid = entry.id if status in (PublishStatus.PUBLISHED,
                                     PublishStatus.HIDDEN,
                                     PublishStatus.SCHEDULED) else status.name

        date = arrow.get(entry.local_date)

        dest_basename = format_str.format(
            date=date.format('YYYYMMDD'),
            time=date.format('HHmmss'),
            id=eid,
            status=status.name,
            sid=sid,
            title=entry.title,
            slug=entry.slug_text,
            type=entry.entry_type).strip()
        dest_basename = re.sub(r' +', ' ', dest_basename)

        if dest_basename != basename:
            while True:
                # UniqueSlugify will bump the suffix until it doesn't collide
                dest_path = os.path.join(path, fname_slugify(dest_basename) + ext)
                if not os.path.exists(dest_path):
                    break

            if verbose:
                print(f'{entry.file_path} -> {dest_path}')

            if not os.path.isfile(entry.file_path):
                LOGGER.warning('File %s does not exist; is the index up-to-date?', entry.file_path)
            elif os.path.exists(dest_path):
                LOGGER.warning('File %s already exists', dest_path)
            elif not dry_run:
                try:
                    os.rename(entry.file_path, dest_path)
                except OSError:
                    LOGGER.exception('Error moving %s to %s', entry.file_path, dest_path)
                entry.file_path = dest_path
                orm.commit()


def setup(app):
    """ Register the CLI commands with the command parser """
    app.cli.add_command(publ_cli)
