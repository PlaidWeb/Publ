# model.py
""" Database schema for the content index """

from __future__ import absolute_import

import logging
import threading
import datetime
from enum import Enum

from pony import orm
from pony.orm.dbapiprovider import StrConverter

from . import config

db = orm.Database()  # pylint: disable=invalid-name
lock = threading.Lock()  # pylint: disable=invalid-name

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name

# schema version; bump this number if it changes
SCHEMA_VERSION = 100


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


class EnumConverter(StrConverter):
    """ Convert between an Enum and an int
        for database storage purposes. Source:
        https://stackoverflow.com/q/31395663/318857
    """

    def validate(self, val):
        if not isinstance(val, Enum):
            raise ValueError('Must be an Enum.  Got {}'.format(type(val)))
        return val

    def py2sql(self, val):
        return val.name

    def sql2py(self, value):
        # Any enum type can be used, so py_type ensures the correct one is used
        # to create the enum instance
        return self.py_type[value]


class FileFingerprint(db.Entity):
    """ File modification time """
    file_path = orm.Required(str, unique=True)
    fingerprint = orm.Required(str)


class Entry(db.Entity):
    """ Indexed entry """
    file_path = orm.Required(str)
    category = orm.Required(str)
    status = orm.Required(PublishStatus)

    # UTC-normalized, for ordering and visibility
    utc_date = orm.Required(datetime.datetime)

    # arbitrary timezone, for pagination
    local_date = orm.Required(datetime.datetime)

    # The actual displayable date
    display_date = orm.Required(datetime.datetime)

    slug_text = orm.Required(str)
    entry_type = orm.Required(str)
    redirect_url = orm.Optional(str)
    title = orm.Optional(str)

    aliases = orm.Set("PathAlias")

    orm.composite_index(category, entry_type, utc_date)
    orm.composite_index(category, entry_type, local_date)

    def is_visible(self, date=None):
        """ Returns if this entry is visible relative to the provided date

        date -- a datetime for reference, or None for right now (default)
        """
        return (
            self.status == PublishStatus.PUBLISHED or
            (
                self.status == PublishStatus.SCHEDULED and
                self.utc_date <= (date or arrow.utcnow().datetime)
            )
        )

    def is_visible_future(self):
        """ Returns if this entry will ever be visible """
        return (self.status == PublishStatus.PUBLISHED or
                self.status == PublishStatus.SCHEDULED)

    def in_category(self, category, recurse=False):
        """ Returns if this entry is within the specified category

        recurse -- whether to test for recursive subcategories as well
        """

        if not category and recurse:
            return True

        if recurse:
            return self.category == category or self.category.startswith(category + '/')

        return self.category == category


class Category(db.Entity):
    """ Metadata for a category """
    category = orm.Required(str, unique=True)
    file_path = orm.Required(str)
    sort_name = orm.Required(str)

    aliases = orm.Set("PathAlias")


class PathAlias(db.Entity):
    """ Path alias mapping """
    path = orm.Required(str, unique=True)
    url = orm.Optional(str)
    entry = orm.Optional(Entry)
    category = orm.Optional(Category)
    template = orm.Optional(str)


class Image(db.Entity):
    """ Image metadata """
    file_path = orm.Required(str, unique=True)
    checksum = orm.Required(str)
    width = orm.Required(int)
    height = orm.Required(int)
    transparent = orm.Required(bool)
    fingerprint = orm.Required(str)


def setup():
    """ Set up the database """

    db.bind(**config.database_config, create_db=True)
    db.provider.converter_classes.append((Enum, EnumConverter))

    db.generate_mapping(create_tables=True)

    version = None
    with orm.db_session:
        try:
            version = GlobalConfig['schema_version'].int_value
        except orm.ObjectNotFound:
            pass

    if version and version != SCHEMA_VERSION:
        logger.info("Schema version %d -> %d; rebuilding database",
                    version, SCHEMA_VERSION)
        # rebuild the tables
        db.drop_all_tables(with_all_data=True)
        db.create_tables()
        version = None
    elif version:
        logger.info("Schema version %d", version)
    else:
        logger.info("Schema version unset")

    if not version:
        with orm.db_session:
            logger.info("Updating schema version")
            db.GlobalConfig(key='schema_version', int_value=SCHEMA_VERSION)
            orm.commit()
