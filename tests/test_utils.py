""" tests of publ.utils class """

import flask

from publ import utils


def test_callable_proxy():
    """ Tests of the CallableProxy class """

    def wrapped_func(retval="default"):
        return retval

    proxy = utils.CallableProxy(wrapped_func)

    assert proxy() == "default"
    assert proxy(1) == 1
    assert proxy(True) is True
    assert proxy(False) is False

    app = flask.Flask(__name__)
    with app.test_request_context("/"):
        assert proxy.upper() == "DEFAULT"
        assert bool(proxy)
        assert len(proxy) == 7
        assert str(proxy) == "default"
        assert list(proxy) == ['d', 'e', 'f', 'a', 'u', 'l', 't']
        assert proxy[3] == 'a'

        assert proxy == "default"
        assert 't' in proxy
        assert proxy + "foo" == "defaultfoo"


def test_callable_proxy_caching():
    """ Test the caching-ness of CallableProxy's default """

    app = flask.Flask(__name__)
    app.secret_key = 'bogus'

    stash = {'call_count': 0}

    def wrapped_func():
        stash['call_count'] += 1
        return flask.request.path

    proxy = utils.CallableProxy(wrapped_func)

    with app.test_request_context("/foo/bar"):
        # within same path the call should only happen once
        assert str(proxy) == "/foo/bar"
        assert stash['call_count'] == 1
        assert str(proxy) == "/foo/bar"
        assert stash['call_count'] == 1

    with app.test_request_context("/foo/bar"):
        # cached value should remain cached
        assert str(proxy) == "/foo/bar"
        assert stash['call_count'] == 1

    with app.test_request_context("/foo/baz"):
        # different path should call it again
        assert str(proxy) == "/foo/baz"
        assert stash['call_count'] == 2

    with app.test_request_context("/foo/baz"):
        # different user should call it again
        flask.session['me'] = 'test:cachebuster'
        assert str(proxy) == "/foo/baz"
        assert stash['call_count'] == 3


def test_truecallable_proxy():
    """ Tests of TrueCallableProxy """

    stash = {'call_count': 0}

    def wrapped_func():
        stash['call_count'] += 1
        return False

    proxy = utils.TrueCallableProxy(wrapped_func)

    app = flask.Flask(__name__)
    with app.test_request_context('/foo'):
        assert stash['call_count'] == 0
        if proxy:
            assert stash['call_count'] == 0
        else:
            raise AssertionError("proxy should have been truthy!")


def test_callablevalue():
    """ Tests of CallableValue """
    proxy = utils.CallableValue("flonk")
    falsy = utils.CallableValue(False)

    app = flask.Flask(__name__)
    with app.test_request_context("/bar"):
        assert proxy == "flonk"
        assert len(proxy) == 5
        assert proxy + "foo" == "flonkfoo"
        assert not falsy


def test_tagset_membership():
    """ Membership tests for TagSet """
    from publ.utils import TagSet

    items = ('a', 'S', 'd', 'F')
    others = ('Q', 'w', 'E', 'r')
    tags = TagSet(items)

    assert bool(tags)
    assert not bool(TagSet())
    assert not bool(TagSet([]))
    assert not bool(TagSet({}))

    assert len(tags) == 4

    assert hash(TagSet(('a', 's', 'd'))) == hash(TagSet(('s', 'd', 'a')))
    assert hash(TagSet(('a', 's', 'd'))) == hash(TagSet(('A', 'S', 'D')))
    assert hash(TagSet(items)) != hash(TagSet(others))

    for item in items:
        assert item in tags
        assert item.lower() in tags
        assert item.upper() in tags
        assert item.casefold() in tags

    for item in tags:
        assert item.casefold() in {t.casefold() for t in items}

    for item in others:
        assert item not in tags
        assert item.lower() not in tags
        assert item.upper() not in tags
        assert item.casefold() not in tags


def test_tagset_operators():
    """ Test operators  on TagSet """
    from publ.utils import TagSet

    assert TagSet(('a', 's', 'D', 'F')) == TagSet(('A', 'S', 'd', 'f'))
    assert TagSet(('a', 's', 'D', 'F')) == {'A', 'S', 'd', 'f'}
    assert TagSet(('a', 's', 'd', 'f')) != TagSet(('a', 's', 'd'))
    assert TagSet(('a', 's', 'd', 'f')) != {'a', 's', 'd'}

    assert TagSet(('a', 'S', 'd')) | TagSet(('A', 's', 'D', 'F')) == TagSet(('a', 's', 'd', 'f'))
    assert TagSet(('a', 'S', 'd')) | {'A', 's', 'D', 'F'} == TagSet(('a', 's', 'd', 'f'))

    assert TagSet(('a', 'S', 'd')) & TagSet(('a', 'D')) == TagSet(('A', 'd'))
    assert TagSet(('a', 'S', 'd')) & {'a', 'D'} == TagSet(('A', 'd'))

    assert TagSet(('a', 's', 'd', 'f')) ^ TagSet(
        ('A', 'F', 'G', 'h')) == TagSet(('s', 'd', 'g', 'h'))
    assert TagSet(('a', 's', 'd', 'f')) ^ {'A', 'F', 'G', 'h'} == TagSet(('s', 'd', 'g', 'h'))

    assert TagSet(('a', 's', 'd', 'f')) - {'A', 'D', 'g', 'G'} == {'s', 'f'}

    assert TagSet(('1', '2', '3')) < TagSet(('1', '2', '3', '4'))
    assert TagSet(('1', '2', '3')) < {'1', '2', '3', '4'}

    assert TagSet(('1', '2', '3')) <= TagSet(('1', '2', '3', '4'))
    assert TagSet(('1', '2', '3')) <= {'1', '2', '3', '4'}

    # pylint:disable=unneeded-not
    assert not TagSet(('a', 's', 'd')) < TagSet(('a', 's', 'd'))
    assert not TagSet(('a', 's', 'd')) < TagSet(('q', 'w', 'e'))
    assert not TagSet(('a', 's', 'd')) <= TagSet(('q', 'w', 'e'))
