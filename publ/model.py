# model.py
""" Database schema for the content index """

from __future__ import absolute_import

import logging
import threading
from enum import Enum

import peewee
from peewee import Proxy, Model, IntegerField, DateTimeField, CharField
import playhouse.db_url

from . import config

DATABASE_PROXY = Proxy()
lock = threading.Lock()  # pylint: disable=invalid-name

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name

# Schema version; bump this whenever an existing table changes
SCHEMA_VERSION = 6


class BaseModel(Model):
    """ Base model for our content index """
    # pylint: disable=too-few-public-methods

    class Meta:
        """ database configuration """
        database = DATABASE_PROXY


class PublishStatus(Enum):
    """ The status of the entry """
    DRAFT = 0  # Entry should not be rendered
    HIDDEN = 1  # Entry should be shown via direct link, but not shown on a view
    PUBLISHED = 2  # Entry is visible
    SCHEDULED = 3  # Entry will be visible in the future

    @staticmethod
    class Field(IntegerField):
        """ Database mapping for PublishStatis """

        def db_value(self, value):
            """ map enum to database column """
            return value.value

        def python_value(self, value):
            """ map database column to enum """
            return PublishStatus(value)


class Global(BaseModel):
    """ key-value storage for the index itself """
    key = CharField(unique=True)
    int_value = IntegerField(null=True)
    str_value = CharField(null=True)


class FileMTime(BaseModel):
    """ File modification time """
    file_path = CharField(unique=True)
    stat_mtime = IntegerField()  # At least on SQLite, this is Y2k38-ready


class Entry(BaseModel):
    """ Indexed entry """
    file_path = CharField()
    category = CharField()
    status = PublishStatus.Field()
    entry_date = DateTimeField()  # UTC-normalized, for queries
    display_date = DateTimeField()  # arbitrary timezone, for display
    slug_text = CharField()
    entry_type = CharField()
    redirect_url = CharField(null=True)
    title = CharField(null=True)

    class Meta:
        """ meta info """
        # pylint: disable=too-few-public-methods
        indexes = (
            (('category', 'entry_type', 'entry_date'), False),
        )


class PathAlias(BaseModel):
    """ Path alias mapping """
    path = CharField(unique=True)
    redirect_url = CharField(null=True)
    redirect_entry = peewee.ForeignKeyField(
        Entry,
        null=True,
        backref='aliases')


class Image(BaseModel):
    """ Image metadata """
    file_path = CharField(unique=True)
    checksum = CharField()
    width = IntegerField()
    height = IntegerField()
    transparent = peewee.BooleanField()
    mtime = IntegerField()

ALL_TYPES = [
    Global,
    FileMTime,
    Entry,
    PathAlias,
    Image,
]


def setup():
    """ Set up the database """
    database = playhouse.db_url.connect(config.database)
    DATABASE_PROXY.initialize(database)

    rebuild = False
    try:
        cur_version = Global.get(key='schema_version').int_value
        logger.info("Current schema version: %s", cur_version)
        rebuild = cur_version != SCHEMA_VERSION
    except:  # pylint: disable=bare-except
        logger.info("Schema information not found")
        rebuild = True

    if rebuild:
        logger.info("Updating database schema")
        database.drop_tables(ALL_TYPES)

    database.create_tables(ALL_TYPES)

    version_record, _ = Global.get_or_create(key='schema_version')
    version_record.int_value = SCHEMA_VERSION
    version_record.save()
