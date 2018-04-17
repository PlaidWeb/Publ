# markdown.py
""" handler for markdown formatting """

import misaka
import flask

import pygments
import pygments.formatters
import pygments.lexers

ENABLED_EXTENSIONS = [
    'fenced-code', 'footnotes', 'strikethrough', 'highlight', 'math', 'math-explicit'
]


class HtmlRenderer(misaka.HtmlRenderer):
    """ Customized renderer for enhancing Markdown formatting """

    def __init__(self, config):
        super().__init__()
        self._config = config

    def image(self, raw_url, title, alt):
        """ Adapt a standard Markdown image to a generated rendition """

        image_spec = '{}{}'.format(raw_url, title and ' "{}"'.format(title))

        return ('<span class="error">Image renditions not yet implemented '
                + '<!-- alt={} image_spec={} --></span>'.format(
                    alt, image_spec))

    def blockcode(self, text, lang):
        """ Pass a code fence through pygments """
        if lang and self._config.get('highlight_syntax', 'True'):
            try:
                lexer = pygments.lexers.get_lexer_by_name(lang, stripall=True)
            except pygments.lexers.ClassNotFound:
                lexer = None

            if lexer:
                formatter = pygments.formatters.HtmlFormatter()  # pylint: disable=no-member
                return pygments.highlight(text, lexer, formatter)

        return '\n<div class="highlight"><pre>{}</pre></div>\n'.format(
            flask.escape(text.strip()))


def to_html(text, **kwargs):
    """ Convert Markdown text to HTML """

    # TODO add image rendition config
    # http://github.com/fluffy-critter/Publ/issues/9
    processor = misaka.Markdown(HtmlRenderer(config=kwargs),
                                extensions=ENABLED_EXTENSIONS)
    return processor(text)
