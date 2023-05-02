""" Unit tests for entry objects """

import flask
from pony import orm

from publ import entry, model

from . import PublMock


def test_get_permissions():
    """ Test the permissions on entry attributes """
    app = PublMock()

    # Test logged-out
    with app.test_request_context('/'), orm.db_session():
        record = model.Entry.get(id=107)
        authed = entry.Entry.load(record)

        assert not authed.authorized
        assert authed.permalink() == '/107'

        assert not authed.title()
        assert authed.title(always_show=True) == 'Friends + specific user'

        assert 'title' not in authed
        assert not authed.get('title')
        assert not authed.get_all('title')

        assert authed.get('title', always_show=True) == 'Friends + specific user'
        assert authed.get_all('title', always_show=True) == ['Friends + specific user']

        assert 'uuid' in authed
        assert authed.uuid == 'e63eff37-042b-58bf-8330-ace5a5db6ab7'
        assert authed.get('uuid') == 'e63eff37-042b-58bf-8330-ace5a5db6ab7'
        assert authed.get_all('uuid') == ['e63eff37-042b-58bf-8330-ace5a5db6ab7']

    # test logged-in as user
    with app.test_request_context('/'), orm.db_session():
        flask.session['me'] = 'test:specific'

        record = model.Entry.get(id=107)
        authed = entry.Entry.load(record)

        assert authed.authorized
        assert authed.permalink() == '/auth/107-Friends-specific-user'

        assert 'title' in authed
        assert authed.title() == 'Friends + specific user'
        assert authed.get('title') == 'Friends + specific user'
        assert authed.get_all('title') == ['Friends + specific user']

    # test logged-in as admin
    with app.test_request_context('/'), orm.db_session():
        flask.session['me'] = 'admin'

        record = model.Entry.get(id=107)
        authed = entry.Entry.load(record)

        assert authed.authorized
        assert authed.permalink() == '/auth/107-Friends-specific-user'

        assert 'title' in authed
        assert authed.title() == 'Friends + specific user'
        assert authed.get('title') == 'Friends + specific user'
        assert authed.get_all('title') == ['Friends + specific user']
