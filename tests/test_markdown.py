""" Tests of Markdown renderer """
# pylint:disable=missing-function-docstring

from publ import markdown


def test_render_title():
    assert markdown.render_title("This *is* a test") == "This <em>is</em> a test"
    assert markdown.render_title("This *is* a test", markup=False) == "This is a test"
    assert markdown.render_title("This is ~~not~~ a test", markup=False) == "This is a test"
    assert markdown.render_title("This is <s>not</s> a test", markup=False) == "This is a test"
    assert markdown.render_title("This & That", markup=False) == "This & That"
    assert markdown.render_title("This & That", markup=True) == "This &amp; That"

    assert markdown.render_title('The "sun" is a liberal myth',
                                 markup=False, smartquotes=False) == 'The "sun" is a liberal myth'
    assert markdown.render_title('The "sun" is a liberal myth',
                                 markup=False, smartquotes=True) == 'The “sun” is a liberal myth'
    assert markdown.render_title('The "sun" is a liberal myth',
                                 markup=True, smartquotes=False) == \
        'The &quot;sun&quot; is a liberal myth'
    assert markdown.render_title('The "sun" is a liberal myth',
                                 markup=True, smartquotes=True) == \
        'The &ldquo;sun&rdquo; is a liberal myth'
