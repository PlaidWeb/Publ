# model.py
# Content indices et al

from peewee import *
import playhouse.db_url
from enum import Enum
import uuid

import config

database = playhouse.db_url.connect(config.database)

def atomic():
    return database.atomic()

''' Boilerplate for schema migration '''

class BaseModel(Model):
    class Meta:
        database = database

''' Our types '''

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

class EntryType(Enum):
    ENTRY = 0
    PAGE = 1

    @staticmethod
    class Field(IntegerField):
        def db_value(self,value):
            return value.value
        def python_value(self,value):
            return EntryType(value)

class FileMTime(BaseModel):
    file_path = CharField(unique=True)
    stat_mtime = IntegerField()  # TODO investigate if this is Y2k38-ready

class Entry(BaseModel):
    file_path = CharField()
    category = CharField()
    status = PublishStatus.Field()
    entry_type = EntryType.Field()
    entry_date = DateTimeField()
    slug_text = CharField()
    redirect_url = CharField(null=True)
    title = CharField(null=True)

    class Meta:
        indexes = (
            (('entry_type', 'category', 'entry_date'), False),
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
    FileMTime,
    Entry,
    PathAlias,
    Image,
]

def create_tables():
    database.create_tables(all_types)
