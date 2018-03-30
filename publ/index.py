# index.py
# Content indices et al

from peewee import *
import playhouse.db_url
from enum import Enum

import config

database = playhouse.db_url.connect(config.database)

def atomic():
    return database.atomic()

''' Boilerplate for schema migration '''

class BaseModel(Model):
    class Meta:
        database = database

    @staticmethod
    def update_schema(check_update,from_version):
        ''' Implement this to migrate a database from an older version, and return the current version of this table.

        Only process updates if check_update is true. Example:

            if check_update and from_version < 1:
                migrate(
                    migrator.add_column('BlahTable', 'foo', BlahTable.foo),
                    migrator.add_column('BlahTable', 'bar', BlahTable.baz), # changed from 'bar' to 'baz' in verison 2
                )
            if check_update and from_version < 2:
                migrate(
                    migrator.rename_column('BlahTable', 'bar', 'baz'),
                )
            return 2
        '''
        return 0

class Global(BaseModel):
    ''' Settings for the site itself (schema version, generic global config, etc.) '''
    key = CharField(unique=True)
    int_value = IntegerField(null=True)
    string_value = CharField(null=True)

    @staticmethod
    def update_schema(check_update,from_version):
        ''' Hook for migrating schemata, e.g. table names '''
        return 0

''' Our types '''

class PublishStatus(Enum):
    DRAFT = 0
    PUBLISHED = 1
    HIDDEN = 2

    @property
    def is_visible(self):
        return self == PublishStatus.PUBLISHED

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


class Entry(BaseModel):
    file_path = CharField()
    category = CharField()
    status = PublishStatus.Field()
    entry_type = EntryType.Field()
    entry_date = DateTimeField()
    slug_text = CharField()
    redirect_url = CharField(null=True)

    class Meta:
        indexes = (
            (('entry_type', 'category', 'entry_date'), False),
        )

class LegacyUrl(BaseModel):
    incoming_url = CharField(unique=True)
    redirect_url = CharField()

class Image(BaseModel):
    file_path = CharField(unique=True)
    md5sum = CharField()
    mtime = DateTimeField()


''' Table management '''

all_types = [
    Global,    # MUST come first

    Entry,
    LegacyUrl,
    Image,
]

def create_tables():
    with database.atomic():
        database.create_tables(all_types, safe=True)
        for table in all_types:
            schemaVersion, created = Global.get_or_create(key='schemaVersion.' + table.__name__)
            schemaVersion.int_value = table.update_schema(not created, schemaVersion.int_value)
            schemaVersion.save()

def drop_all_tables(i_am_really_sure=False):
    ''' Call this if you need to nuke everything and restart. Only for development purposes, hopefully. '''
    if not i_am_really_sure:
        raise "You are not really sure. Call with i_am_really_sure=True to proceed."
    with database.atomic():
        for table in all_types:
            database.drop_table(table)
