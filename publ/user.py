""" Authenticated user functionality """

import collections
import configparser
import ast
import datetime

import arrow
import flask
from pony import orm
from werkzeug.utils import cached_property

from . import caching, config, model


@caching.cache.memoize(timeout=30)
def get_groups(username):
    """ Get the group membership for the given username """

    @caching.cache.memoize(timeout=30)
    def load_groups():
        # We only want empty keys; \000 is unlikely to turn up in a well-formed text file
        cfg = configparser.ConfigParser(delimiters=(
            '\000'), allow_no_value=True, interpolation=None)
        # disable authentication lowercasing; usernames should only be case-densitized
        # by the auth backend
        cfg.optionxform = lambda option: option
        cfg.read(config.user_list)

        groups = collections.defaultdict(set)

        # populate the group list for each member
        for group, members in cfg.items():
            for member in members.keys():
                groups[member].add(group)

        return groups

    groups = load_groups()
    result = set()
    pending = collections.deque()

    pending.append(username)

    while pending:
        check = pending.popleft()
        if check not in result:
            result.add(check)
            pending += groups.get(check, [])

    return result


class User(caching.Memoizable):
    """ An authenticated user """

    def __init__(self, me):
        self._me = me

    def _key(self):
        return self._me

    def __lt__(self, other):
        return self._me < other._me

    @cached_property
    def name(self):
        """ The federated identity name of the user """
        return self._me

    @cached_property
    def groups(self):
        """ The group memberships of the user """
        return get_groups(self._me)

    @property
    def is_admin(self):
        """ Returns whether this user has administrator permissions """
        return config.admin_group and config.admin_group in self.groups


def get_active():
    """ Get the active user and add it to the request stash """
    if flask.session.get('me'):
        return User(flask.session['me'])

    return None


def log_access(record, cur_user, authorized):
    """ Log a user's access to the audit log """
    log_values = {
        'date': arrow.utcnow().datetime,
        'entry': record,
        'authorized': authorized
    }
    if cur_user:
        log_values['user'] = cur_user.name
        log_values['user_groups'] = str(cur_user.groups)
    model.AuthLog(**log_values)


@orm.db_session(immediate=True)
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
def known_users(days=30):
    """ Get the users known to the system, as a list of (user,last_seen) """
    since = (arrow.utcnow() - datetime.timedelta(days=days)).datetime
    query = model.KnownUser.select(lambda x: x.last_seen >= since)

    return [(User(record.user), arrow.get(record.last_seen).to(config.timezone)) for record in query]


LogEntry = collections.namedtuple(
    'LogEntry', ['date', 'entry', 'user', 'user_groups', 'authorized'])


@orm.db_session()
def auth_log(days=30):
    """ Get the logged accesses to each entry """
    from . import entry  # pylint:disable=cyclic-import

    since = (arrow.utcnow() - datetime.timedelta(days=days)).datetime
    query = model.AuthLog.select(lambda x: x.date >= since)

    def _to_set(groups):
        try:
            return ast.literal_eval(groups)
        except (ValueError, SyntaxError):
            return set(groups.split(','))

    return [LogEntry(arrow.get(record.date).to(config.timezone),
                     entry.Entry(record.entry),
                     User(record.user),
                     _to_set(record.user_groups),
                     record.authorized)
            for record in query]
