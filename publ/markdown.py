# markdown.py
""" markdown formatting functionality """

import logging
import re
import urllib.parse

import flask
import misaka
import pygments
import pygments.formatters
import pygments.lexers

from . import config, html_entry, image, links, utils

LOGGER = logging.getLogger(__name__)


class HtmlRenderer(misaka.HtmlRenderer):
    """ Customized renderer for enhancing Markdown formatting

    Constructor arguments:

    config -- The configuration for the Markdown tags
    search_path -- Directories to look in for resolving relatively-linked files
    """

    def __init__(self, args, search_path, entry_id, footnote_buffer):
        # pylint:disable=no-member
        super().__init__(0, args.get('xhtml') and misaka.HTML_USE_XHTML or 0)

        self._config = args
        self._search_path = search_path
        self._entry_id = entry_id

        self._footnote_link = args.get('footnotes_link') or ''
        self._footnote_buffer = footnote_buffer
        self._footnote_ofs = len(footnote_buffer) if footnote_buffer else 0

    @staticmethod
    def footnotes(_):
        """ Actual footnote rendering is handled by the caller """
        return None

    def _footnote_num(self, num):
        return num + self._footnote_ofs

    def _footnote_id(self, num, anchor):
        return '{anchor}_e{eid}_fn{num}'.format(
            anchor=anchor,
            eid=self._entry_id,
            num=self._footnote_num(num))

    def _footnote_url(self, num, anchor):
        return urllib.parse.urljoin(self._footnote_link,
                                    '#' + self._footnote_id(num, anchor))

    def footnote_ref(self, num):
        """ Render a link to this footnote """
        return '{sup}{link}{content}</a></sup>'.format(
            sup=utils.make_tag('sup', {
                'id': self._footnote_id(num, "r"),
                'class': self._config.get('footnotes_class', False)
            }),
            link=utils.make_tag('a', {
                'href': self._footnote_url(num, "d"),
                'rel': 'footnote'
            }),
            content=self._footnote_num(num))

    def footnote_def(self, content, num):
        """ Render the footnote body, deferring it if so configured """
        if self._footnote_buffer is not None:
            LOGGER.debug("footnote_def %d: %s", num, content)

            # Insert the return anchor before the end of the first content block
            before, partition, after = content.partition('</p>')
            text = '{li}{before}&nbsp;{link}{icon}</a>{partition}{after}</li>'.format(
                li=utils.make_tag('li', {
                    'id': self._footnote_id(num, "d")
                }),
                before=before,
                link=utils.make_tag('a', {
                    'href': self._footnote_url(num, "r"),
                    'rev': 'footnote'
                }),
                icon=self._config.get('footnotes_return', '↩'),
                partition=partition,
                after=after,
            )

            self._footnote_buffer.append(text)

        return ' '

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

        container_args = utils.prefix_normalize({**self._config, **container_args})

        spec_list = image.get_spec_list(image_specs, container_args)

        remain = 0
        for (spec, show) in spec_list:
            text += self._render_image(spec, show,
                                       container_args,
                                       alt)
            if not show:
                remain += 1

        if remain and 'more_text' in container_args:
            more_text = container_args['more_text'].format(
                count=len(spec_list),
                remain=remain)
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
                                   {'class': container_args.get('div_class') or False,
                                    'style': container_args.get('div_style') or False}),
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

        link = links.resolve(link, self._search_path,
                             self._config.get('absolute'))

        return '{}{}</a>'.format(
            utils.make_tag('a', {
                'href': link,
                'title': title if title else False
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

    def _render_image(self, spec, show, container_args, alt_text=None):
        """ Render an image specification into an <img> tag """

        try:
            path, image_args, title = image.parse_image_spec(spec)
        except Exception as err:  # pylint: disable=broad-except
            LOGGER.exception("Got error on spec %s: %s", spec, err)
            return ('<span class="error">Couldn\'t parse image spec: ' +
                    '<code>{}</code> {}</span>'.format(flask.escape(spec),
                                                       flask.escape(str(err))))

        composite_args = {**container_args, **image_args}

        try:
            img = image.get_image(path, self._search_path)
        except Exception as err:  # pylint: disable=broad-except
            LOGGER.exception("Got error on image %s: %s", path, err)
            return ('<span class="error">Error loading image {}: {}</span>'.format(
                flask.escape(spec), flask.escape(str(err))))

        return img.get_img_tag(title,
                               alt_text,
                               **composite_args,
                               _show_thumbnail=show,
                               _mark_rewritten=True)


def to_html(text, args, search_path, entry_id=None, footnote_buffer=None):
    """ Convert Markdown text to HTML.

    footnote_buffer -- a list that will contain <li>s with the footnote items, if
    there are any footnotes to be found.
    """

    # first process as Markdown
    processor = misaka.Markdown(HtmlRenderer(args,
                                             search_path,
                                             footnote_buffer=footnote_buffer,
                                             entry_id=entry_id),
                                args.get('markdown_extensions') or
                                config.markdown_extensions)
    text = processor(text)

    # convert smartquotes, if so configured.
    # We prefer setting 'smartquotes' but we fall back to the negation of
    # 'no_smartquotes' for backwards compatibility with a not-well-considered
    # API.
    if args.get('smartquotes', not args.get('no_smartquotes', False)):
        text = misaka.smartypants(text)

    # now filter through html_entry to rewrite local src/href links
    text = html_entry.process(text, args, search_path)

    return flask.Markup(text)


class TitleRenderer(HtmlRenderer):
    """ A renderer that is suitable for rendering out page titles and nothing else """

    def __init__(self):
        super().__init__({}, [], entry_id=None, footnote_buffer=None)

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


def render_title(text, markup=True, no_smartquotes=False, markdown_extensions=None):
    """ Convert a Markdown title to HTML """

    # If the title starts with something that looks like a list, save it for
    # later
    pfx, text = re.match(r'([0-9. ]*)(.*)', text).group(1, 2)

    text = pfx + misaka.Markdown(TitleRenderer(),
                                 extensions=markdown_extensions
                                 or config.markdown_extensions)(text)

    if not markup:
        text = html_entry.strip_html(text)

    if not no_smartquotes:
        text = misaka.smartypants(text)

    return flask.Markup(text)
