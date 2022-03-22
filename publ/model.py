# model.py
""" Database schema for the content index """

# pylint: disable=too-few-public-methods

import datetime
import logging
from enum import Enum

from pony import orm

db = orm.Database()  # pylint: disable=invalid-name

DbEntity: orm.core.Entity = db.Entity

LOGGER = logging.getLogger(__name__)

# schema version; bump this number if it changes
SCHEMA_VERSION = 22


class GlobalConfig(DbEntity):
    """ Global configuration data """
    key = orm.PrimaryKey(str)
    int_value = orm.Optional(int)


class PublishStatus(Enum):
    """ The status of the entry """
    DRAFT = 0       # Entry should not be rendered

    HIDDEN = 1      # Entry should be shown via direct link, but not shown on a view
    UNLISTED = 1    # Synonym for HIDDEN

    PUBLISHED = 2   # Entry is visible

    SCHEDULED = 3   # Entry will be visible in the future

    GONE = 4        # Entry is gone, won't be coming back
    DELETED = 4     # synonym for GONE

    ILLEGAL = 5     # taken down for legal reasons (error code 451)
    BURNT = 5
    BURNED = 5
    DMCA = 5

    TEAPOT = 6      # RFC 2324


class AliasType(Enum):
    """ The type of PathAlias mapping """
    REDIRECT = 0    # Redirect to the canon URL
    MOUNT = 1       # Display the URL at the alias


class FileFingerprint(DbEntity):
    """ File modification time """
    file_path = orm.PrimaryKey(str)
    fingerprint = orm.Required(str)
    file_mtime = orm.Required(float)


class Entry(DbEntity):
    """ Indexed entry """
    file_path = orm.Required(str, unique=True)
    category = orm.Optional(str)
    status = orm.Required(int)

    # UNIX epoch, for ordering and visibility
    utc_timestamp = orm.Required(int, size=64)

    # arbitrary timezone, for pagination
    local_date = orm.Required(datetime.datetime)

    # The actual displayable date - stored as string to guarantee the timezone
    # is maintained
    display_date = orm.Required(str)

    slug_text = orm.Optional(str)
    entry_type = orm.Optional(str)
    redirect_url = orm.Optional(str)   # maps to Redirect-To

    title = orm.Optional(str)
    sort_title = orm.Optional(str)

    aliases = orm.Set("PathAlias")
    tags = orm.Set("EntryTagged")

    auth = orm.Set("EntryAuth")
    auth_log = orm.Set("AuthLog")

    attachments = orm.Set("Entry", reverse="attached")
    attached = orm.Set("Entry", reverse="attachments")

    canonical_path = orm.Optional(str)

    orm.composite_index(category, entry_type, utc_timestamp)
    orm.composite_index(category, entry_type, local_date)
    orm.composite_index(category, entry_type, sort_title)

    @property
    def visible(self) -> bool:
        """ Returns true if the entry should be viewable """
        return self.status in (PublishStatus.HIDDEN.value,
                               PublishStatus.PUBLISHED.value,
                               PublishStatus.SCHEDULED.value)

    def is_authorized(self, user) -> bool:
        """ Returns whether the entry is visible to the specified user """
        if not self.auth:
            return True

        LOGGER.debug("Computing auth for entry %s user %s", self.file_path, user)

        if user and user.is_admin:
            LOGGER.debug("User is admin")
            return True

        result = False
        for auth in self.auth.order_by(EntryAuth.order):
            LOGGER.debug("  %d test=%s allowed=%s", auth.order, auth.user_group, auth.allowed)
            if auth.user_group == '*':
                # Special group * refers to all logged-in users
                result = auth.allowed == (user is not None)
                LOGGER.debug("  result->%s", result)

            else:
                if user and auth.user_group in user.auth_groups:
                    result = auth.allowed
                    LOGGER.debug("  result->%s", result)

        LOGGER.debug("Final result: %s", result)
        return result


class EntryTag(DbEntity):
    """ Tags available for entries """
    key = orm.PrimaryKey(str)
    name = orm.Required(str)

    entries = orm.Set("EntryTagged")


class EntryTagged(DbEntity):
    """ Actual tag membership for entries """
    entry = orm.Required(Entry)
    tag = orm.Required(EntryTag)
    hidden = orm.Required(bool)

    orm.composite_key(entry, tag)
    orm.composite_key(tag, entry)


class Category(DbEntity):
    """ Metadata for a category """

    category = orm.Optional(str, unique=True)
    file_path = orm.Required(str)
    sort_name = orm.Optional(str)

    aliases = orm.Set("PathAlias")


class PathAlias(DbEntity):
    """ Path alias mapping """
    path = orm.PrimaryKey(str)
    entry = orm.Optional(Entry)
    category = orm.Optional(Category)
    template = orm.Optional(str)
    alias_type = orm.Required(int)  # reflects AliasType


class Image(DbEntity):
    """ Image metadata """
    file_path = orm.PrimaryKey(str)
    checksum = orm.Required(str)
    fingerprint = orm.Required(str)

    width = orm.Optional(int)
    height = orm.Optional(int)
    transparent = orm.Optional(bool)

    is_asset = orm.Required(bool, default=False)
    asset_name = orm.Optional(str, index=True)


class EntryAuth(DbEntity):
    """ An authentication record for an entry """
    order = orm.Required(int)
    entry = orm.Required(Entry)
    user_group = orm.Required(str)
    allowed = orm.Required(bool)

    orm.composite_key(entry, order)


class KnownUser(DbEntity):
    """ Users who are known to the system """
    user = orm.PrimaryKey(str)
    last_login = orm.Optional(datetime.datetime)
    last_seen = orm.Required(datetime.datetime, index=True)
    last_token = orm.Optional(datetime.datetime)
    profile = orm.Optional(orm.Json)


class AuthLog(DbEntity):
    """ Authentication log for private entries """
    date = orm.Required(datetime.datetime, index=True)
    entry = orm.Required(Entry, index=True)
    user = orm.Required(str, index=True)
    user_groups = orm.Optional(str)  # group membership at the time of access
    authorized = orm.Required(bool, index=True)

    orm.PrimaryKey(entry, user)


def reset():
    """ Completely reset the database """
    LOGGER.info("Rebuilding schema")
    try:
        db.drop_all_tables(with_all_data=True)
        db.create_tables()
    except Exception as error:  # pylint:disable=broad-except
        raise RuntimeError("Unable to upgrade schema automatically; please " +
                           "delete the existing database and try again.") from error


def setup(config):
    """ Set up the database """
    rebuild = False

    try:
        db.bind(**config)
    except OSError:
        # Attempted to connect to a file-based database where the file didn't
        # exist
        db.bind(**config, create_db=True)

    try:
        db.generate_mapping(create_tables=True)
        with orm.db_session:
            version = GlobalConfig.get(key='schema_version')
            if not version or version.int_value != SCHEMA_VERSION:
                LOGGER.info("Wanted schema %d, got %s", SCHEMA_VERSION, version)
                rebuild = True
            else:
                LOGGER.info("Existing database has schema version %d",
                            version.int_value)

    except Exception:  # pylint:disable=broad-except
        LOGGER.exception("Error mapping schema")
        rebuild = True

    if rebuild:
        reset()

    with orm.db_session:
        if not GlobalConfig.get(key='schema_version'):
            LOGGER.info("setting schema version to %d", SCHEMA_VERSION)
            GlobalConfig(key='schema_version',
                         int_value=SCHEMA_VERSION)
            orm.commit()
