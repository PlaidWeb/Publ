# markdown.py
""" handler for markdown formatting """

from __future__ import absolute_import

import logging
import html.parser
import re

import misaka
import flask

import pygments
import pygments.formatters
import pygments.lexers

from . import image, utils

TITLE_EXTENSIONS = (
    'strikethrough', 'math',
)

ENABLED_EXTENSIONS = (
    'tables', 'fenced-code', 'footnotes', 'strikethrough', 'highlight', 'superscript', 'math',
)

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


class HtmlRenderer(misaka.HtmlRenderer):
    """ Customized renderer for enhancing Markdown formatting

    Constructor arguments:

    config -- The configuration for the Markdown tags
    search_path -- Directories to look in for resolving relatively-linked files
    """

    def __init__(self, config, search_path):
        # pylint: disable=no-member
        super().__init__(0, config.get('xhtml') and misaka.HTML_USE_XHTML or 0)

        self._config = config
        self._search_path = search_path

    def image(self, raw_url, title='', alt=''):
        """ Adapt a standard Markdown image to a generated rendition set.

        Container arguments used (in addition to the rendition tags):

        div_class -- The CSS class name to use on any wrapper div
        div_style -- Additional CSS styles to apply to the wrapper div
        count -- The maximum number of images to show at once
        more_text -- If there are more than `count` images, add this text indicating
            that there are more images to be seen. This string gets two template
            arguments, `{count}` which is the total number of images in the set,
            and `{remain}` which is the number of images omitted from the set.
        more_link -- If `more_text` is shown, this will format the text as a link to this location.
        more_class -- If `more_text` is shown, wraps it in a `<div>` with this class.
        """
        # pylint: disable=too-many-locals

        text = ''

        image_specs = raw_url
        if title:
            image_specs += ' "{}"'.format(title)

        alt, container_args = image.parse_alt_text(alt)

        container_args = {**self._config, **container_args}

        spec_list, original_count = image.get_spec_list(
            image_specs, container_args)

        for spec in spec_list:
            text += self._render_image(spec,
                                       container_args,
                                       alt)

        if original_count > len(spec_list) and 'more_text' in container_args:
            more_text = container_args['more_text'].format(
                count=original_count,
                remain=original_count - len(spec_list))
            if 'more_link' in container_args:
                more_text = '{a}{text}</a>'.format(
                    text=more_text,
                    a=utils.make_tag('a', {'href': container_args['more_link']}))
            if 'more_class' in container_args:
                more_text = '{div}{text}</div>'.format(
                    text=more_text,
                    div=utils.make_tag('div', {'class': container_args['more_class']}))
            text += flask.Markup(more_text)

        if text and (container_args.get('div_class') or
                     container_args.get('div_style')):
            text = '{tag}{text}</div>'.format(
                tag=utils.make_tag('div',
                                   {'class': container_args.get('div_class'),
                                    'style': container_args.get('div_style')}),
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

        # if the content contains a top-level div then don't wrap it in a <p>
        # tag
        if content.startswith('<div') and content.endswith('</div>'):
            return '\n' + content + '\n'

        text = '<p>' + content + '</p>'
        text = re.sub(r'<p>\s*</p>', r'', text)
        return text or ' '

    def _remap_path(self, path):
        """ Remap a path to an appropriate URL """

        if not path.startswith('//') and not '://' in path:
            entry = utils.find_entry(path, self._search_path)
            if entry:
                return entry.link(self._config)
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
            img = image.get_image(path, self._search_path)
        except Exception as err:  # pylint: disable=broad-except
            logger.exception("Got error on image %s: %s", path, err)
            return ('<span class="error">Error loading image {}: {}</span>'.format(
                flask.escape(spec), flask.escape(str(err))))

        return img.get_img_tag(title, alt_text, **composite_args)


def to_html(text, config, search_path):
    """ Convert Markdown text to HTML """
    processor = misaka.Markdown(HtmlRenderer(config, search_path),
                                extensions=ENABLED_EXTENSIONS)

    text = processor(text)
    if not config.get('no_smartquotes'):
        text = misaka.smartypants(text)

    return flask.Markup(text)


class TitleRenderer(HtmlRenderer):
    """ A renderer that is suitable for rendering out page titles and nothing else """

    def __init__(self):
        super().__init__({}, [])

    @staticmethod
    def paragraph(content):
        """ Passthrough """
        return content

    @staticmethod
    def list(content, is_ordered, is_block):
        """ Passthrough """
        # pylint: disable=unused-argument
        return content

    @staticmethod
    def listitem(content, is_ordered, is_block):
        """ Just add the * back on """
        # pylint: disable=unused-argument
        if not is_ordered:
            return '* ' + content
        raise ValueError("Not sure how we got here")

    @staticmethod
    def header(content, level):
        """ Passthrough """
        # pylint: disable=unused-argument
        return content


class HTMLStripper(html.parser.HTMLParser):
    """ A utility class to strip HTML from a string; based on
    https://stackoverflow.com/a/925630/318857 """

    def __init__(self):
        super().__init__()

        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.fed = []

    def handle_data(self, data):
        """ Append the text data """
        self.fed.append(data)

    def get_data(self):
        """ Concatenate the output """
        return ''.join(self.fed)

    def error(self, message):
        """ Deprecated, per https://bugs.python.org/issue31844 """
        return message


def render_title(text, markup=True, no_smartquotes=False):
    """ Convert a Markdown title to HTML """

    # HACK: If the title starts with something that looks like a list, save it
    # for later
    pfx, text = re.match(r'([0-9. ]*)(.*)', text).group(1, 2)
    text = pfx + misaka.Markdown(TitleRenderer(),
                                 extensions=TITLE_EXTENSIONS)(text)

    if not markup:
        strip = HTMLStripper()
        strip.feed(text)
        text = strip.get_data()

    if not no_smartquotes:
        text = misaka.smartypants(text)

    return flask.Markup(text)
