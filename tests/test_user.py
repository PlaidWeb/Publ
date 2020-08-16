""" User permissions tests """
# pylint:disable=missing-docstring


import flask
from pony import orm

from publ import user

from . import PublMock


def test_user_permissions(mocker):
    test_config = """
[admin]
some:admin
some:other-admin

[group1]
group2
test:user1

[group2]
test:user2

[mutual1]
mutual2

[mutual2]
mutual1
"""
    mocker.patch('builtins.open', mocker.mock_open(read_data=test_config))

    app = PublMock()
    with app.test_request_context("https://foo.bar/baz"):
        testuser = user.User('some:admin')
        assert testuser.is_admin
        assert testuser.identity == 'some:admin'

        testuser = user.User('some:other-admin')
        assert testuser.is_admin

        testuser = user.User('unspecified')
        assert not testuser.is_admin
        assert testuser.identity == 'unspecified'
        assert testuser.groups == set()
        assert testuser.auth_groups == {'unspecified'}

        testuser = user.User('test:user1')
        assert testuser.identity == 'test:user1'
        assert testuser.groups == {'group1'}
        assert testuser.auth_groups == {'test:user1', 'group1'}

        testuser = user.User('test:user2')
        assert testuser.identity == 'test:user2'
        assert testuser.groups == {'group1', 'group2'}
        assert testuser.auth_groups == {'test:user2', 'group1', 'group2'}

        testuser = user.User('mutual1')
        assert testuser.auth_groups == {'mutual1', 'mutual2'}

        testuser = user.User('mutual2')
        assert testuser.auth_groups == {'mutual1', 'mutual2'}

    with app.test_request_context('/'):
        flask.session['me'] = 'test:user2'
        testuser = user.get_active()
        assert testuser.identity == 'test:user2'
        assert testuser.auth_groups == {'test:user2', 'group1', 'group2'}
        assert not testuser.is_admin

        # test the cachingness
        flask.session.pop('me')
        testuser2 = user.get_active()
        assert testuser == testuser2
        assert testuser2.identity == 'test:user2'


def test_alternate_config(mocker):
    test_config = """
[admin]
test:one

[real_admin]
test:two
"""
    mocker.patch('builtins.open', mocker.mock_open(read_data=test_config))

    app = PublMock({'admin_group': 'real_admin'})
    with app.test_request_context('/'):
        flask.session['me'] = 'test:one'
        assert not user.get_active().is_admin

    with app.test_request_context('/'):
        flask.session['me'] = 'test:two'
        assert user.get_active().is_admin


def test_logging():
    app = PublMock()
    with app.test_request_context('/'):
        flask.session['me'] = 'logged:user'
        user.log_user()
        assert user.get_active().last_seen
        assert user.get_active().last_login is None
        assert not user.get_active().profile


def test_profile():
    from authl import disposition
    app = PublMock()
    with app.test_request_context('/'):
        user.register(disposition.Verified('some:user', '', {'name': 'visible name'}))
        flask.session['me'] = 'some:user'
        assert user.get_active().profile
        assert user.get_active().name == 'visible name'
        assert user.get_active().last_login
        assert user.get_active().last_seen

    with app.test_request_context('/'), orm.db_session():
        flask.session['me'] = 'https://example.user/~blah'
        assert user.get_active().name == 'example.user/~blah'
        assert user.get_active().last_login is None


def test_user_token():
    app = PublMock()
    with app.test_request_context('/'):
        flask.session['me'] = 'token:user'
        token = user.get_active().token(lifetime=1800)
    with app.test_request_context('/', headers={'Authorization': f'Bearer {token}'}):
        cur_user = user.get_active()
        assert cur_user.identity == 'token:user'
        assert cur_user.auth_type == 'token'
