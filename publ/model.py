# model.py
""" Database schema for the content index """

from __future__ import absolute_import

import logging
import datetime
from enum import Enum

from pony import orm

from . import config

db = orm.Database()  # pylint: disable=invalid-name

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name

# schema version; bump this number if it changes
SCHEMA_VERSION = 4


class GlobalConfig(db.Entity):
    """ Global configuration data """
    key = orm.PrimaryKey(str)
    int_value = orm.Optional(int)


class PublishStatus(Enum):
    """ The status of the entry """
    DRAFT = 0  # Entry should not be rendered
    HIDDEN = 1  # Entry should be shown via direct link, but not shown on a view
    PUBLISHED = 2  # Entry is visible
    SCHEDULED = 3  # Entry will be visible in the future
    GONE = 4  # Entry is gone, won't be coming back
    DELETED = 4  # synonym for GONE


class FileFingerprint(db.Entity):
    """ File modification time """
    file_path = orm.PrimaryKey(str)
    fingerprint = orm.Required(str)
    file_mtime = orm.Required(float, index=True)


class Entry(db.Entity):
    """ Indexed entry """
    file_path = orm.Required(str)
    category = orm.Optional(str)
    status = orm.Required(int)

    # UTC-normalized, for ordering and visibility
    utc_date = orm.Required(datetime.datetime)

    # arbitrary timezone, for pagination
    local_date = orm.Required(datetime.datetime)

    # The actual displayable date
    display_date = orm.Required(datetime.datetime)

    slug_text = orm.Optional(str)
    entry_type = orm.Optional(str)
    redirect_url = orm.Optional(str)   # maps to Redirect-To
    title = orm.Optional(str)

    aliases = orm.Set("PathAlias")

    entry_template = orm.Optional(str)  # maps to Entry-Template

    orm.composite_index(category, entry_type, utc_date)
    orm.composite_index(category, entry_type, local_date)


class Category(db.Entity):
    """ Metadata for a category """

    category = orm.Optional(str)
    file_path = orm.Required(str)
    sort_name = orm.Optional(str)

    aliases = orm.Set("PathAlias")


class PathAlias(db.Entity):
    """ Path alias mapping """
    path = orm.PrimaryKey(str)
    url = orm.Optional(str)
    entry = orm.Optional(Entry)
    category = orm.Optional(Category)
    template = orm.Optional(str)


class Image(db.Entity):
    """ Image metadata """
    file_path = orm.PrimaryKey(str)
    checksum = orm.Required(str)
    width = orm.Required(int)
    height = orm.Required(int)
    transparent = orm.Required(bool)
    fingerprint = orm.Required(str)


def setup():
    """ Set up the database """
    try:
        db.bind(**config.database_config)
    except OSError:
        # Attempted to connect to a file-based database where the file didn't
        # exist
        db.bind(**config.database_config, create_db=True)

    rebuild = True

    try:
        db.generate_mapping(create_tables=True)
        with orm.db_session:
            version = GlobalConfig.get(key='schema_version')
            if version and version.int_value != SCHEMA_VERSION:
                logger.info("Existing database has schema version %d",
                            version.int_value)
            else:
                rebuild = False
    except:  # pylint:disable=bare-except
        logger.exception("Error mapping schema")

    if rebuild:
        logger.info("Rebuilding schema")
        try:
            db.drop_all_tables(with_all_data=True)
            db.create_tables()
        except:
            raise RuntimeError("Unable to upgrade schema automatically; please " +
                               "delete the existing database and try again.")

    with orm.db_session:
        if not GlobalConfig.get(key='schema_version'):
            logger.info("setting schema version to %d", SCHEMA_VERSION)
            GlobalConfig(key='schema_version',
                         int_value=SCHEMA_VERSION)
            orm.commit()
