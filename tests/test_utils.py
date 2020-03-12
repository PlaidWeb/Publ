""" tests of publ.utils module """
# pylint:disable=missing-function-docstring

import flask
import pytest

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
        assert proxy
        assert stash['call_count'] == 0


def test_callablevalue():
    """ Tests of CallableValue """
    proxy = utils.CallableValue("flonk")
    falsy = utils.CallableValue(False)

    app = flask.Flask(__name__)
    with app.test_request_context("/bar"):
        assert proxy == "flonk"
        assert len(proxy) == 5
        assert proxy + "foo" == "flonkfoo"
        assert proxy
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


def test_parse_tuple_string():
    """ test of parse_tuple_string() """
    assert utils.parse_tuple_string((1, 2, 3)) == (1, 2, 3)
    assert utils.parse_tuple_string([1, 2, 3]) == (1, 2, 3)
    assert utils.parse_tuple_string("1,2,3") == (1, 2, 3)
    assert utils.parse_tuple_string("a,,", bool) == (True, False, False)
    with pytest.raises(Exception):
        utils.parse_tuple_string("a,b,c", float)
    assert utils.parse_tuple_string(None) is None


def test_make_tag():
    """ test of utils.make_tag """

    assert utils.make_tag('a', {'href': 'foo'}, False) == '<a href="foo">'
    assert utils.make_tag('a',
                          [('href', 'foo'), ('href', 'bar')],
                          True) == '<a href="foo" href="bar" />'
    with pytest.raises(Exception):
        utils.make_tag('a', (('href', 'foo')))

    app = flask.Flask(__name__)
    with app.test_request_context():
        proxy = utils.CallableValue("<hello>")
        assert utils.make_tag('a', {'href': proxy}) == '<a href="&lt;hello&gt;">'

    escaped = flask.Markup("&amp;")
    assert utils.make_tag('a', {'href': escaped}) == '<a href="&amp;">'


def test_listlike():
    """ test functions involving the ListLike inference class """
    assert utils.is_list((1, 2, 3))
    assert utils.is_list([])
    assert utils.is_list([1, 2, 3])
    assert utils.is_list({1, 2, 3})
    assert utils.is_list(frozenset((1, 2, 3)))
    assert utils.is_list(utils.TagSet(('1', '2', 'A', 'a')))
    assert not utils.is_list("")
    assert not utils.is_list("foo")
    assert not utils.is_list(123)
    assert not utils.is_list(True)
    assert not utils.is_list(None)

    assert utils.as_list([1, 2, 3]) == [1, 2, 3]
    assert utils.as_list((1, 2, 3)) == (1, 2, 3)
    assert utils.as_list("foo") == ("foo",)
    assert utils.as_list(True) == (True,)
    assert utils.as_list(None) == ()


def test_parse_date():
    """ tests for the date parser """
    import arrow
    from publ import config

    def make_date(year=None, month=None, day=None):
        return arrow.Arrow(year=year or 1,
                           month=month or 1,
                           day=day or 1,
                           tzinfo=config.timezone)

    with pytest.raises(ValueError):
        utils.parse_date("not a date")
    with pytest.raises(ValueError):
        utils.parse_date("12345678")
    with pytest.raises(ValueError):
        utils.parse_date("")

    assert utils.parse_date('1978-06-14') == (make_date(1978, 6, 14), 'day', utils.DAY_FORMAT)
    assert utils.parse_date('19780614') == (make_date(1978, 6, 14), 'day', utils.DAY_FORMAT)

    assert utils.parse_date('1983-07') == (make_date(1983, 7), 'month', utils.MONTH_FORMAT)
    assert utils.parse_date('198307') == (make_date(1983, 7), 'month', utils.MONTH_FORMAT)

    assert utils.parse_date("1979") == (make_date(1979), 'year', utils.YEAR_FORMAT)

    assert utils.parse_date('19810505_w') == (make_date(1981, 5, 4), 'week', utils.WEEK_FORMAT)


def test_find_file():
    """ tests for the file finder """
    assert utils.find_file("anything", []) is None

    assert utils.find_file("anything", ["tests/templates"]) is None
    assert utils.find_file("auth", ["tests/templates"]) is None

    assert utils.find_file("index.html",
                           ("tests/templates")
                           ) == "tests/templates/index.html"
    assert utils.find_file("index.html",
                           ("tests/templates", "tests/templates/auth")
                           ) == "tests/templates/index.html"
    assert utils.find_file("index.html",
                           ("tests/templates/auth", "tests/templates")
                           ) == "tests/templates/auth/index.html"


def test_static_url():
    """ tests for the static URL builder """
    app = flask.Flask("tests", static_folder="asdf")
    with app.test_request_context("https://foo.bar/poiupoiupoiu"):
        assert utils.static_url("thing", absolute=False) == "/asdf/thing"
        assert utils.static_url("thong", absolute=True) == "https://foo.bar/asdf/thong"


def test_remap_link_target():
    """ test the target remapper """
    app = flask.Flask("tests", static_folder="feedme")
    with app.test_request_context("https://feed.me/blah/merry"):
        assert utils.remap_link_target("@fred") == "/feedme/fred"
        assert utils.remap_link_target("@fred", absolute=True) == "https://feed.me/feedme/fred"
        assert utils.remap_link_target("daphne") == "daphne"
        assert utils.remap_link_target("daphne", absolute=True) == "https://feed.me/blah/daphne"


def test_get_category():
    import os.path
    assert utils.get_category(os.path.join("foo", "bar", "entry.html")) == "foo/bar"


def test_remap_args():
    """ test the argument parser remapper """
    args = {'foo': 'bar', 'quuz': 'quux'}
    assert utils.remap_args(args, {}) == args
    assert utils.remap_args(args, {"foo": "poiu"}) == args
    assert utils.remap_args(args, {"foo": "quuz"})['foo'] == 'quux'


def test_prefix_normalize():
    """ test the prefix remapping thing """
    args = {'here': '1',
            'prefix_here':
            '2', 'prefix_there': '3',
            'anywhere': '4',
            'prefix': 'prefix_'}
    assert utils.prefix_normalize(args) == {
        'here': '2',
        'there': '3',
        'anywhere': '4',
        'prefix': 'prefix_'
    }
