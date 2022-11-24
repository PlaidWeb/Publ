
""" Authenticated user functionality """

import ast
import collections
import configparser
import datetime
import logging
import typing
import urllib.parse
from typing import Optional

import arrow
import flask
import werkzeug.exceptions as http_error
from pony import orm
from werkzeug.utils import cached_property

from . import caching, model, tokens, utils
from .config import config

LOGGER = logging.getLogger(__name__)


@caching.cache.memoize(timeout=5)
def get_groups(identity: str, include_self: bool = True) -> typing.Set[str]:
    """ Get the group membership for the given identity """

    @caching.cache.memoize(timeout=10)
    def load_groups() -> typing.DefaultDict[str, typing.Set[str]]:
        # We only want empty keys; \000 is unlikely to turn up in a well-formed text file
        cfg = configparser.ConfigParser(delimiters=(
            '\000'), allow_no_value=True, interpolation=None)
        # disable authentication lowercasing; identities should only be case-desensitized
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

    pending.append(identity)

    while pending:
        check = pending.popleft()
        if check not in result:
            if include_self or check != identity:
                result.add(check)
            pending += groups.get(check, [])

    return result


class User(caching.Memoizable):
    """ An authenticated user """

    def __init__(self, identity: str,
                 auth_type: typing.Optional[str] = None,
                 scope: typing.Optional[str] = None):
        """ Initialize the user object.

        :param str identity: The federated identity name
        :param str auth_type: The authentication mechanism
        :param str scope: The user's access scope
        """

        self._identity = identity
        self._auth_type = auth_type
        self._scope = scope

    def _key(self):
        return self._identity, self._auth_type, self._scope

    def __lt__(self, other):
        return self.identity < other.identity

    @cached_property
    def identity(self):
        """ The federated identity name of the user """
        return self._identity

    @cached_property
    def humanize(self) -> str:
        """ A humanized version of the identity string """
        url = self.profile.get('profile_url', self._identity)
        parsed = urllib.parse.urlparse(url)
        return ''.join(p for p in (
            f'{parsed.scheme}:' if parsed.scheme not in ('http', 'https') else '',
            parsed.netloc,
            parsed.path,
        ))

    @cached_property
    def name(self) -> str:
        """ The readable name of the user """
        if 'name' in self.profile:
            return self.profile['name']

        return self.humanize

    @property
    def profile(self) -> dict:
        """ Get the user's profile """
        return self._info[0]

    @cached_property
    def groups(self) -> typing.Set[str]:
        """ The group memberships of the user, for display purposes """
        return get_groups(self._identity, False)

    @cached_property
    def auth_groups(self) -> typing.Set[str]:
        """ The group memberships of the user, for auth purposes """
        return get_groups(self._identity, True)

    @cached_property
    def is_admin(self) -> bool:
        """ Returns whether this user has administrator permissions """
        return bool(config.admin_group and config.admin_group in self.auth_groups)

    @cached_property
    def auth_type(self):
        """ The type of user authentication (session, token, etc.) """
        return self._auth_type

    @cached_property
    def scope(self):
        """ The permission scope of the user """
        return self._scope

    @cached_property
    def _info(self) -> typing.Tuple[dict,
                                    typing.Optional[datetime.datetime],
                                    typing.Optional[datetime.datetime]]:
        """ Gets the user info from the database

        :returns: profile, last_login, last_seen
        """
        with orm.db_session():
            record = model.KnownUser.get(user=self._identity)
            if record:
                return (record.profile.copy(),
                        record.last_login,
                        record.last_seen)
        return {}, None, None

    @property
    def last_login(self) -> typing.Optional[arrow.Arrow]:
        """ Get the latest known login time for the user, if any """
        date = self._info[1]
        return arrow.get(date).to(config.timezone) if date else None

    @property
    def last_seen(self) -> arrow.Arrow:
        """ Get the latest known active time for the user """
        date = self._info[2]
        return arrow.get(date).to(config.timezone) if date else None

    def token(self, lifetime: int, scope: Optional[str] = None) -> str:
        """ Get a bearer token for this user """
        return tokens.get_token(self.identity, lifetime, scope)


@utils.stash
def get_active() -> typing.Optional[User]:
    """ Get the active user """
    if 'token_error' in flask.g:
        # We already got an error trying to parse an access token
        return None

    if 'Authorization' in flask.request.headers:
        token = tokens.parse_authorization_header(flask.request.headers['Authorization'])
        try:
            return User(token['me'], 'token', token.get('scope'))
        except http_error.HTTPException as error:
            flask.g['token_error'] = error.description
            raise

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
            'user': cur_user.identity,
            'user_groups': str(cur_user.groups) if cur_user.groups else ''
        }
        log_entry = model.AuthLog.get(entry=record, user=cur_user.identity)
        if log_entry:
            log_entry.set(**values)
        else:
            model.AuthLog(**values)


def _get_group_set(groups):
    try:
        return ast.literal_eval(groups)
    except (ValueError, SyntaxError):
        return set(groups.split(',')) if groups else set()


@orm.db_session(retry=5)
def register(verified):
    """ Registers a user from the on_verified Authl hook """
    import authl.disposition
    if isinstance(verified, authl.disposition.Verified):
        LOGGER.info("Got login from user %s with profile %s", verified.identity, verified.profile)
        identity = utils.canonicize_url(verified.identity)
        now = arrow.utcnow().datetime
        values = {
            'last_login': now,
            'last_seen': now,
            'profile': verified.profile
        }

        record = model.KnownUser.get(user=identity)
        if record:
            record.set(**values)
        else:
            record = model.KnownUser(user=identity, **values)

        if (verified.profile
            and 'endpoints' in verified.profile
                and 'ticket_endpoint' in verified.profile['endpoints']):
            tokens.send_auth_ticket(identity, flask.request.url_root,
                                    verified.profile['endpoints']['ticket_endpoint'])


@orm.db_session(retry=5)
def log_user():
    """ Update the user table to see who's been by """
    identity = flask.session.get('me')
    if identity:
        values = {
            'last_seen': arrow.utcnow().datetime,
        }

        record = model.KnownUser.get(user=identity)
        if record:
            record.set(**values)
        else:
            record = model.KnownUser(user=identity, **values)


@orm.db_session()
def known_users(days=None):
    """ Get the users known to the system, as a list of (user,last_seen) """
    query = model.KnownUser.select()
    if days:
        since = (arrow.utcnow() - datetime.timedelta(days=days)).datetime
        query = orm.select(e for e in query if e.last_seen >= since)

    query = query.order_by(orm.desc(model.KnownUser.last_seen))

    return [(User(record.user), arrow.get(record.last_seen).to(config.timezone))
            for record in query]


LogEntry = collections.namedtuple(
    'LogEntry', ['date', 'entry', 'user', 'user_groups', 'authorized'])


@orm.db_session()
def auth_log(start=0, count=100):
    """ Get the logged accesses to each entry """
    query = model.AuthLog.select().order_by(orm.desc(model.AuthLog.date))[start:]

    return [LogEntry(date=arrow.get(record.date).to(config.timezone),
                     entry=record.entry,
                     user=User(record.user),
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
