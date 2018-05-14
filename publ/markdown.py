# markdown.py
""" handler for markdown formatting """

from __future__ import absolute_import

import logging

import misaka
import flask

import pygments
import pygments.formatters
import pygments.lexers

from . import image, utils

ENABLED_EXTENSIONS = [
    'fenced-code', 'footnotes', 'strikethrough', 'highlight', 'math', 'math-explicit'
]

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


class HtmlRenderer(misaka.HtmlRenderer):
    """ Customized renderer for enhancing Markdown formatting """

    def __init__(self, config, image_search_path):
        super().__init__()
        self._config = config
        self._image_search_path = image_search_path

    def image(self, raw_url, title='', alt=''):
        """ Adapt a standard Markdown image to a generated rendition """
        # pylint: disable=too-many-locals

        text = ''

        image_specs = raw_url
        if title:
            image_specs += ' "{}"'.format(title)

        alt, container_args = image.parse_alt_text(alt)

        container_args = {**self._config, **container_args}

        spec_list = image.get_spec_list(image_specs, container_args)

        for spec in spec_list:
            if not spec:
                continue

            text += self._render_image(spec,
                                       container_args,
                                       alt)

        if text and 'div_class' in container_args:
            text = '</p>{tag}{text}</div><p>'.format(
                tag=utils.make_tag('div',
                                   {'class': container_args['div_class']}),
                text=text)

        # if text is ''/falsy then misaka interprets this as a failed parse...
        return text or ' '

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

    def link(self, content, link, title=''):
        """ Emit a link, potentially remapped based on our embed or static rules """

        link = self._remap_path(link)

        return '{}{}</a>'.format(
            utils.make_tag('a', {
                'href': link,
                'title': title if title else None
            }),
            content)

    @staticmethod
    def paragraph(content):
        """ emit a paragraph, stripping out any leading or following empty paragraphs """
        text = '<p>' + content + '</p>'
        if text.startswith('<p></p>'):
            text = text[7:]
        if text.endswith('<p></p>'):
            text = text[:-7]
        return text

    def _remap_path(self, path):
        """ Remap a path to an appropriate URL """
        return utils.remap_link_target(path, self._config.get('absolute'))

    def _render_image(self, spec, container_args, alt_text=None):
        """ Render an image specification into an <img> tag """

        try:
            path, image_args, title = image.parse_image_spec(spec)
        except Exception as err:  # pylint: disable=broad-except
            logger.exception("Got error on spec %s: %s", spec, err)
            return ('<span class="error">Couldn\'t parse image spec: ' +
                    '<code>{}</code> {}</span>'.format(flask.escape(spec),
                                                       flask.escape(str(err))))

        composite_args = {**container_args, **image_args}

        try:
            img = image.get_image(path, self._image_search_path)
        except Exception as err:  # pylint: disable=broad-except
            logger.exception("Got error on image %s: %s", path, err)
            return ('<span class="error">Error loading image {}: {}</span>'.format(
                flask.escape(spec), flask.escape(str(err))))

        return img.get_img_tag(title, alt_text, **composite_args)


def to_html(text, config, image_search_path):
    """ Convert Markdown text to HTML """
    processor = misaka.Markdown(HtmlRenderer(config, image_search_path),
                                extensions=ENABLED_EXTENSIONS)
    return processor(text)
