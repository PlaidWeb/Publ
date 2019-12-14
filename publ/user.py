""" Authenticated user functionality """

import ast
import collections
import configparser
import datetime
import logging
import typing

import arrow
import flask
from pony import orm
from werkzeug.utils import cached_property

from . import caching, config, model, tokens, utils

LOGGER = logging.getLogger(__name__)


@caching.cache.memoize(timeout=30)
def get_groups(username: str, include_self: bool = True) -> typing.Set[str]:
    """ Get the group membership for the given username """

    @caching.cache.memoize(timeout=30)
    def load_groups() -> typing.DefaultDict[str, typing.Set[str]]:
        # We only want empty keys; \000 is unlikely to turn up in a well-formed text file
        cfg = configparser.ConfigParser(delimiters=(
            '\000'), allow_no_value=True, interpolation=None)
        # disable authentication lowercasing; usernames should only be case-densitized
        # by the auth backend
        cfg.optionxform = lambda option: option  # type:ignore
        cfg.read(config.user_list)

        groups: typing.DefaultDict[str, typing.Set[str]] = collections.defaultdict(set)

        # populate the group list for each member
        for group, members in cfg.items():
            for member in members.keys():
                groups[member].add(group)

        return groups

    groups = load_groups()
    result: typing.Set[str] = set()
    pending: typing.Deque[str] = collections.deque()

    pending.append(username)

    while pending:
        check = pending.popleft()
        if check not in result:
            if include_self or check != username:
                result.add(check)
            pending += groups.get(check, [])

    return result


class User(caching.Memoizable):
    """ An authenticated user """

    def __init__(self, name: str,
                 auth_type: typing.Optional[str] = None,
                 scope: typing.Optional[str] = None):
        """ Initialize the user object.

        :param str name: The federated identity name
        :param str auth_type: The authentication mechanism
        :param str scope: The user's access scope
        """

        self._name = name
        self._auth_type = auth_type
        self._scope = scope

    def _key(self):
        return self.name, self.auth_type, self.scope

    def __lt__(self, other):
        return self.name < other.name

    @cached_property
    def name(self):
        """ The federated identity name of the user """
        return self._name

    @cached_property
    def auth_type(self):
        """ The type of user authentication (session, token, etc.) """
        return self._auth_type

    @cached_property
    def scope(self):
        """ The permission scope of the user """
        return self._scope

    @cached_property
    def auth_groups(self) -> typing.Set[str]:
        """ The group memberships of the user, for auth purposes """
        return get_groups(self.name, True)

    @cached_property
    def groups(self) -> typing.Set[str]:
        """ The group memberships of the user, for display purposes """
        return get_groups(self.name, False)

    @property
    def is_admin(self) -> bool:
        """ Returns whether this user has administrator permissions """
        return bool(config.admin_group and config.admin_group in self.groups)


@utils.stash('user')
def get_active() -> typing.Optional[User]:
    """ Get the active user """
    if 'Authorization' in flask.request.headers:
        parts = flask.request.headers['Authorization'].split()
        if parts[0].lower() == 'bearer':
            token = tokens.parse_token(parts[1])
            return User(token['me'], 'token', token.get('scope'))

    if flask.session.get('me'):
        return User(flask.session['me'], 'session')

    return None


@orm.db_session(retry=5)
def log_access(record, cur_user, authorized):
    """ Log a user's access to the audit log """
    LOGGER.info("log_access %s %s %s", record, cur_user, authorized)
    if cur_user:
        values = {
            'date': arrow.utcnow().datetime,
            'entry': record,
            'authorized': authorized,
            'user': cur_user.name,
            'user_groups': str(cur_user.groups) if cur_user.groups else ''
        }
        log_entry = model.AuthLog.get(entry=record, user=cur_user.name)
        if log_entry:
            log_entry.set(**values)
        else:
            model.AuthLog(**values)


@caching.cache.memoize(timeout=30)
def _get_user(username):
    return User(username)


def _get_group_set(groups):
    try:
        return ast.literal_eval(groups)
    except (ValueError, SyntaxError):
        return set(groups.split(',')) if groups else set()


@orm.db_session(retry=5)
def log_user():
    """ Update the user table to see who's been by """
    username = flask.session.get('me')
    if username:
        values = {
            'last_seen': arrow.utcnow().datetime,
        }

        record = model.KnownUser.get(user=username)
        if record:
            record.set(**values)
        else:
            record = model.KnownUser(user=username, **values)


@orm.db_session()
def known_users(days=None):
    """ Get the users known to the system, as a list of (user,last_seen) """
    query = model.KnownUser.select()
    if days:
        since = (arrow.utcnow() - datetime.timedelta(days=days)).datetime
        query = orm.select(e for e in query if e.last_seen >= since)

    return [(_get_user(record.user), arrow.get(record.last_seen).to(config.timezone))
            for record in query]


LogEntry = collections.namedtuple(
    'LogEntry', ['date', 'entry', 'user', 'user_groups', 'authorized'])


@orm.db_session()
def auth_log(days=None, start=0, count=100):
    """ Get the logged accesses to each entry """
    query = model.AuthLog.select()
    if days:
        since = (arrow.utcnow() - datetime.timedelta(days=days)).datetime
        query = orm.select(e for e in query if e.date >= since)
    query = query.order_by(orm.desc(model.AuthLog.date))[start:]

    return [LogEntry(date=arrow.get(record.date).to(config.timezone),
                     entry=record.entry,
                     user=_get_user(record.user),
                     user_groups=_get_group_set(record.user_groups),
                     authorized=record.authorized)
            for record in query[:count]], len(query) - count


@orm.db_session(optimistic=False)
def prune_log(seconds):
    """ Delete log entries which are older than the cutoff """
    since = (arrow.utcnow() - datetime.timedelta(seconds=seconds)).datetime
    LOGGER.debug("Purging auth entries older than %s", since)
    orm.delete(e for e in model.AuthLog if e.date < since)
    orm.delete(e for e in model.KnownUser if e.last_seen < since)
