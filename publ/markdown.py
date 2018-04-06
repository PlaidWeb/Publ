# markdown.py
# handler for markdown formatting

import misaka
import flask
from . import utils

import pygments
import pygments.formatters
import pygments.lexers

# class PublEntryLexer(pygments.lexer.RegexLexer):
#     name = 'PublEntry',
#     aliases = ['publ']


enabled_extensions = (
    misaka.EXT_FENCED_CODE |
    misaka.EXT_TABLES |
    misaka.EXT_FOOTNOTES |
    misaka.EXT_STRIKETHROUGH |
    misaka.EXT_HIGHLIGHT |
    misaka.EXT_MATH |
    misaka.EXT_MATH_EXPLICIT |
    0)


class HtmlRenderer(misaka.HtmlRenderer):
    def __init__(self):
        super().__init__()

    def image(self,raw_url,title,alt):
        if not alt.startswith('@') and not alt.startswith('%'):
            return '<img src="{}" alt="{}" title="{}">'.format(raw_url, alt, title)

        cfg=alt
        image_spec = '{}{}'.format(raw_url, title and ' "{}"'.format(title))
        return "<span class=\"error\">Image renditions not yet implemented <!-- cfg={} image_spec={} --></span>".format(cfg, image_spec)

    def blockcode(self, text, lang):
        print("blockcode", text, lang)
        try:
            lexer = pygments.lexers.get_lexer_by_name(lang, stripall=True)
        except pygments.lexers.ClassNotFound:
            lexer = None

        if lexer:
            formatter = pygments.formatters.HtmlFormatter()
            return pygments.highlight(text, lexer, formatter)
        return '\n<div class="highlight"><pre>{}</pre></div>\n'.format(flask.escape(text.strip()))


class MarkdownText(utils.SelfStrCall):
    def __init__(self, text):
        self._text = text

    def __call__(self, **kwargs):
        md = misaka.Markdown(HtmlRenderer(*kwargs), extensions=enabled_extensions)
        return md(self._text)

