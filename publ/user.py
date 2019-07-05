""" Authenticated user functionality """

import configparser
import collections

from werkzeug.utils import cached_property

from . import caching
from . import config


@caching.cache.memoize()
def get_groups():
    """ Get the user->groups mappings """

    # We only want empty keys; \000 is unlikely to turn up in a well-formed text file
    cfg = configparser.ConfigParser(delimiters=('\000'), allow_no_value=True)
    cfg.read(config.user_list)

    groups = collections.defaultdict(set)

    # populate the group list for each member
    for group, members in cfg.items():
        for member in members.keys():
            groups[member].add(group)

    return groups


class User(caching.Memoizable):
    """ An authenticated user """

    def __init__(self, me):
        self._me = me

    def _key(self):
        return User, self._me

    @cached_property
    def username(self):
        """ The federated identity name of the user """
        return self._me

    @property
    @caching.cache.memoize()
    def groups(self):
        """ The group memberships of the user """
        groups = get_groups()
        result = set()
        pending = collections.deque([self._me])

        while pending:
            check = pending.popleft()
            if check not in result:
                result.add(check)
                pending += groups.get(check, [])

        return result
