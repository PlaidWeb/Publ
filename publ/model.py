# model.py
# Content indices et al

from peewee import *
import playhouse.db_url
from enum import Enum
import uuid
import threading
import logging

import config

database = playhouse.db_url.connect(config.database)
lock = threading.Lock()

logger = logging.getLogger(__name__)

''' Schema version; bump this whenever an existing table changes '''
schema_version = 3

class BaseModel(Model):
    class Meta:
        database = database

class PublishStatus(Enum):
    DRAFT = 0
    HIDDEN = 1
    PUBLISHED = 2
    SCHEDULED = 3

    @staticmethod
    class Field(IntegerField):
        def db_value(self,value):
            return value.value
        def python_value(self,value):
            return PublishStatus(value)

class Global(BaseModel):
    key = CharField(unique=True)
    int_value = IntegerField(null=True)
    str_value = CharField(null=True)

class FileMTime(BaseModel):
    file_path = CharField(unique=True)
    stat_mtime = IntegerField()  # At least on SQLite, this is Y2k38-ready

class Entry(BaseModel):
    file_path = CharField()
    category = CharField()
    status = PublishStatus.Field()
    entry_date = DateTimeField()
    slug_text = CharField()
    entry_type = CharField()
    redirect_url = CharField(null=True)
    title = CharField(null=True)

    class Meta:
        indexes = (
            (('category', 'entry_type', 'entry_date'), False),
        )

class PathAlias(BaseModel):
    path = CharField(unique=True)
    redirect_url = CharField(null=True)
    redirect_entry = ForeignKeyField(Entry, null=True, backref='aliases')

class Image(BaseModel):
    file_path = CharField(unique=True)
    md5sum = CharField()
    mtime = DateTimeField()
    width = IntegerField()
    height = IntegerField()

''' Table management '''

all_types = [
    Global,
    FileMTime,
    Entry,
    PathAlias,
    Image,
]

def create_tables():
    rebuild = False
    try:
        cur_version = Global.get(key='schema_version').int_value
        logger.info("Current schema version: %s", cur_version)
        rebuild = cur_version != schema_version
    except Exception:
        logger.info("Schema version missing")
        rebuild = True

    if rebuild:
        logger.info("Updating database schema")
        database.drop_tables(all_types)

    database.create_tables(all_types)

    version_record, created = Global.get_or_create(key='schema_version')
    version_record.int_value = schema_version
    version_record.save()
