# markdown.py
""" markdown formatting functionality """

import logging
import re
import typing
import urllib.parse

import flask
import misaka
import pygments
import pygments.formatters
import pygments.lexers
import slugify

from . import config, html_entry, image, links, utils

LOGGER = logging.getLogger(__name__)

TocEntry = typing.Tuple[int, str]
TocBuffer = typing.List[TocEntry]

# Allow these tags in TOC entries
TOC_ALLOWED_TAGS = ('sup', 'sub', 'em', 'strong', 'b', 'i', 'code')


class HtmlRenderer(misaka.HtmlRenderer):
    """ Customized renderer for enhancing Markdown formatting

    Constructor arguments:

    config -- The configuration for the Markdown tags
    search_path -- Directories to look in for resolving relatively-linked files
    """

    def __init__(self, args: typing.Dict,
                 search_path: typing.Tuple[str],
                 entry_id: typing.Optional[int],
                 footnote_buffer: typing.Optional[typing.List[str]],
                 toc_buffer: typing.Optional[TocBuffer]):
        # pylint:disable=no-member,too-many-arguments
        super().__init__(0, args.get('xhtml') and misaka.HTML_USE_XHTML or 0)

        self._config = args
        self._search_path = search_path
        self._entry_id = entry_id

        self._footnote_ofs = len(footnote_buffer) if footnote_buffer is not None else 0
        self._footnote_buffer = footnote_buffer

        self._toc_buffer = toc_buffer

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
        return urllib.parse.urljoin(self._config.get('footnotes_link', ''),
                                    '#' + self._footnote_id(num, anchor))

    def footnote_ref(self, num):
        """ Render a link to this footnote """
        if self._config.get('_suppress_footnotes'):
            return '\u200b'  # zero-width space to prevent Misaka fallback

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

    def _header_id(self, content, level, num):
        """ Return a reasonable anchor ID for a heading """
        return '{eid}_h{level}_{num}_{slug}'.format(
            eid=self._entry_id,
            level=level,
            num=num,
            slug=slugify.slugify(content, max_length=32))

    def header(self, content, level):
        """ Make a header with anchor """

        htag = 'h{level}'.format(level=level)
        hid = self._header_id(html_entry.strip_html(content), level,
                              len(self._toc_buffer) + 1)

        atag = utils.make_tag('a', {
            'href': urllib.parse.urljoin(self._config.get('toc_link', ''),
                                         '#' + hid),
            'class': self._config.get('heading_link_class', False),
            **self._config.get('heading_link_config', {})
        })

        if self._toc_buffer is not None:
            LOGGER.debug("append toc: %d %s", level, content)
            self._toc_buffer.append(
                (level,
                 '{atag}{content}</a>'.format(
                     atag=atag,
                     content=html_entry.strip_html(content, allowed_tags=TOC_ALLOWED_TAGS))))

        content = self._config.get('heading_template', '{link}</a>{text}').format(
            link=atag,
            text=content)

        return '{htag_open}{content}</{htag}>'.format(
            htag_open=utils.make_tag(htag, {'id': hid}),
            content=content,
            htag=htag)

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
            return flask.Markup('<span class="error">Couldn\'t parse image spec: ' +
                                '<code>{}</code> {}</span>'.format(flask.escape(spec),
                                                                   flask.escape(str(err))))

        composite_args = {**container_args, **image_args}

        try:
            img = image.get_image(path, self._search_path)
            return img.get_img_tag(title,
                                   alt_text,
                                   **composite_args,
                                   _show_thumbnail=show,
                                   _mark_rewritten=True)
        except Exception as err:  # pylint: disable=broad-except
            LOGGER.exception("Got error on image %s: %s", path, err)
            return flask.Markup('<span class="error">Error loading image {}: {}</span>'.format(
                flask.escape(spec), flask.escape(str(err))))


class ItemCounter(misaka.BaseRenderer):
    """ Just counts the number of things in an entry without any further processing """

    def __init__(self, toc: int = 0, footnote: int = 0):
        super().__init__()
        self.toc = toc
        self.footnote = footnote

    def __str__(self):
        return 'ItemCounter(footnote={footnote},toc={toc})'.format(footnote=self.footnote,
                                                                   toc=self.toc)

    def header(self, content, level):
        """ count this header """
        # pylint:disable=unused-argument
        self.toc += 1

    def footnote_def(self, content, num):
        """ count this footnote """
        # pylint:disable=unused-argument
        self.footnote += 1


def to_html(text, args, search_path,
            entry_id: typing.Optional[int] = None,
            toc_buffer: typing.Optional[TocBuffer] = None,
            footnote_buffer: typing.Optional[typing.List[str]] = None,
            postprocess: bool = True):
    # pylint:disable=too-many-arguments
    """ Convert Markdown text to HTML.

    toc_buffer -- a list of (level,text) for all headings in the entry

    footnote_buffer -- a list that will contain <li>s with the footnote items, if
    there are any footnotes to be found.

    postprocess -- whether to postprocess the buffers for smartypants/HTML/etc.
    """

    footnotes: typing.List[str] = footnote_buffer if footnote_buffer is not None else []
    tocs: TocBuffer = toc_buffer if toc_buffer is not None else []

    # first process as Markdown
    renderer = HtmlRenderer(args,
                            search_path,
                            toc_buffer=tocs,
                            footnote_buffer=footnotes,
                            entry_id=entry_id)
    processor = misaka.Markdown(renderer,
                                args.get('markdown_extensions', config.markdown_extensions))
    text = processor(text)

    if postprocess:
        # convert smartquotes, if so configured.
        # We prefer setting 'smartquotes' but we fall back to the negation of
        # 'no_smartquotes' for backwards compatibility with a not-well-considered
        # API.
        if 'no_smartquotes' in args:
            LOGGER.warning("no_smartquotes is deprecated and will be removed in a future version")
        smartquotes = args.get('smartquotes', not args.get('no_smartquotes', False))
        if smartquotes:
            text = misaka.smartypants(text)
            footnotes[:] = (misaka.smartypants(text) for text in footnotes)
            tocs[:] = ((level, misaka.smartypants(text)) for level, text in tocs)

        # now filter through html_entry to rewrite local src/href links
        text = html_entry.process(text, args, search_path)
        footnotes[:] = (html_entry.process(text, args, search_path)
                        for text in footnotes)

    return flask.Markup(text)


def get_counters(text, args):
    """ Count the number of stateful items in Markdown text. """
    counter = ItemCounter()
    processor = misaka.Markdown(counter,
                                args.get('markdown_extensions', config.markdown_extensions))
    processor(text)
    return counter


class TitleRenderer(HtmlRenderer):
    """ A renderer that is suitable for rendering out page titles and nothing else """

    def __init__(self):
        super().__init__({}, [], entry_id=0, toc_buffer=[], footnote_buffer=[])

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


def render_title(text, markup=True, smartquotes=True, markdown_extensions=None):
    """ Convert a Markdown title to HTML """

    # If the title starts with something that looks like a list, save it for
    # later
    pfx, text = re.match(r'([0-9. ]*)(.*)', text).group(1, 2)

    text = pfx + misaka.Markdown(TitleRenderer(),
                                 extensions=markdown_extensions
                                 or config.markdown_extensions)(text)

    if not markup:
        text = html_entry.strip_html(text)

    if smartquotes:
        text = misaka.smartypants(text)

    return flask.Markup(text)


def toc_to_html(toc: TocBuffer, max_level: int = None) -> str:
    """ Convert a TocBuffer to an appropriate <ol> """

    if not toc:
        return ''

    cur_level = 0
    out = ''

    # preprocess: find the lowest heading level
    min_level = min([level for level, _ in toc])
    toc = [(level - min_level + 1, text) for level, text in toc]

    for level, text in toc:
        if max_level is None or level <= max_level:
            if level > cur_level:
                # open sublists
                out += '<ol><li>' * (level - cur_level)
            else:
                # close sublists and the prior entry from this level
                out += '</li></ol>' * (cur_level - level) + '</li><li>'
            out += text
            cur_level = level

    out += '</li></ol>' * cur_level
    return out
