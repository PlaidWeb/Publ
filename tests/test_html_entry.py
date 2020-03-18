""" tests of publ.html_entry module """
# pylint:disable=missing-function-docstring


def test_process_passthrough():
    from publ.html_entry import process

    passthrough = '''<!DOCTYPE html>
<html><head>
<link rel="alternate" href="//example.com/" />
<title>This entry should pass through unscathed</title></head>
<body><h1>This entry should not be modified at all.</h1>

<p>This entry is one of those ones which shouldn't have anything that gets
modified in it, and shouldn't require an
<a href="https://flask.palletsprojects.com/en/1.1.x/appcontext/">application
context</a> to function.</p>

<img src="//example.com/some-image.png">

<br/><br/>

<!-- commentary -->

</body></html>'''
    assert process(passthrough, {}, ()) == passthrough

    assert process('<img data-publ-rewritten src="do_not_rewrite.jpg" width=400 height=400>',
                   {}, ()) == '<img src="do_not_rewrite.jpg" width="400" height="400">'


def test_process_attr_rewrites():
    import flask
    from publ.html_entry import process

    app = flask.Flask(__name__, static_folder="bleh")
    with app.test_request_context("https://foo.bar/baz"):
        assert process('<a href="@something">foo</a>', {}, ()) == \
            '<a href="/bleh/something">foo</a>'
        assert process('<a href="@something">bar</a>', {'absolute': True}, ()) == \
            '<a href="https://foo.bar/bleh/something">bar</a>'

        assert process('<div $data-something="@something" />', {}, ()) == \
            '<div data-something="/bleh/something" />'
        assert process('<div $data-something="@something" />', {'absolute': True}, ()) == \
            '<div data-something="https://foo.bar/bleh/something" />'


def test_process_strip_html():
    from publ.html_entry import process

    assert process('<a href="foo">bar</a>', {'markup': False}, ()) == "bar"


def test_strip_html():
    from publ.html_entry import strip_html

    assert strip_html("foobar") == "foobar"

    doc = '<a href="zxcv" class="mew">blah<sup>boo</sup></a><br/>'

    assert strip_html(doc) == "blahboo"

    assert strip_html(doc, ('sup')) == "blah<sup>boo</sup>"

    assert strip_html(doc, ('a'), ('href')) == '<a href="zxcv">blahboo</a>'

    assert strip_html(doc, remove_elements=('sup')) == 'blah'

    assert strip_html(doc, ('br')) == 'blahboo<br/>'

    assert strip_html("this &amp; that") == "this & that"
