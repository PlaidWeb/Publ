# markdown.py
""" markdown formatting functionality """
# pylint:disable=consider-using-f-string

import html
import logging
import re
import typing
import urllib.parse
from typing import Optional

import flask
import misaka
import pygments
import pygments.formatters
import pygments.lexers
import slugify

from . import html_entry, image, links, utils
from .config import config

LOGGER = logging.getLogger(__name__)

TocEntry = typing.Tuple[int, str]
TocBuffer = typing.List[TocEntry]

# Allow these tags in TOC entries
TOC_ALLOWED_TAGS = ('sup', 'sub',
                    'em', 'strong',
                    'b', 'i',
                    'code',
                    'del', 'add', 'mark')

# Remove these tags from plaintext-style conversions
PLAINTEXT_REMOVE_ELEMENTS = ('del', 's', 'table')


class ItemCounter(misaka.BaseRenderer):
    """ Just counts the number of things in an entry without any further processing """

    def __init__(self, toc: int = 0, footnote: int = 0, code_blocks: int = 0):
        super().__init__()
        self.toc = toc
        self.footnote = footnote
        self.code_blocks = code_blocks

    def __str__(self):
        return 'ItemCounter(footnote={footnote},toc={toc},code_blocks={bc})'.format(
            footnote=self.footnote,
            toc=self.toc,
            bc=self.code_blocks
        )

    def copy(self):
        """ Return a copy of this counter """
        return ItemCounter(self.toc, self.footnote, self.code_blocks)

    def header(self, content, level):
        """ count this header """
        # pylint:disable=unused-argument
        self.toc += 1

    def footnote_def(self, content, num):
        """ count this footnote """
        # pylint:disable=unused-argument
        self.footnote += 1

    def blockcode(self, text, lang):
        """ count this blockcode """
        # pylint:disable=unused-argument
        self.code_blocks += 1


class HtmlCodeFormatter(pygments.formatters.HtmlFormatter):  # pylint:disable=no-member
    """ Customized code block formatter

    Constructor arguments:

    line_id_prefix -- the prefix for each line's <span> id
    link_base -- the base URL for the line links
    """
    # pylint:disable=too-few-public-methods

    def __init__(self,
                 line_id_prefix: str,
                 link_base: typing.Union[str, bool],
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.line_id_prefix = line_id_prefix
        self.link_base = link_base

    def wrap(self, source):
        """ called by pygments """
        # pylint:disable=unused-argument
        return self._wrap_code(source)

    def _wrap_div(self, inner):
        """ Don't wrap the inner code in a <div> """
        # pylint:disable=no-self-use
        yield from inner

    def _wrap_code(self, source):
        """ Format the lines as table row-likes """
        line_number = 0
        for i, line in source:
            if i == 1:
                line_number += 1
                line_id = f"{self.line_id_prefix}L{line_number}"

                yield 1, (utils.make_tag('span', {'class': 'line',
                                                  'id': line_id})
                          + (utils.make_tag('a', {
                              'class': 'line-number',
                              'href': self.link_base + '#' + line_id})
                             + '</a>' if self.link_base else '')
                          + utils.make_tag('span', {'class': 'line-content'})
                          + line.rstrip('\n')
                          + '</span></span>\n')


class HtmlRenderer(misaka.HtmlRenderer):
    """ Customized renderer for enhanced Markdown formatting

    :param dict config: The configuration for the Markdown tags
    :param list search_path: Directories to look in for resolving relatively-linked files
    :param int entry_id: the numeric entry ID
    :param list footnote_buffer: the buffer of footnote entries so far
    :param list toc_buffer: the buffer of TOC entries so far
    :param ItemCounter counter: item count accumulator

    For configuration values, see the individual Markdown implementation functions,
    :py:func:`HtmlRenderer.image`, and py:mod:`publ.image`.

    """

    def __init__(self, args: typing.Dict,
                 search_path: typing.Tuple[str],
                 entry_id: typing.Optional[int],
                 footnote_buffer: typing.Optional[typing.List[str]],
                 toc_buffer: typing.Optional[TocBuffer],
                 counter: ItemCounter):
        # pylint:disable=no-member,too-many-arguments
        super().__init__(0, args.get('xhtml') and misaka.HTML_USE_XHTML or 0)

        self._config = args
        self._search_path = search_path
        self._entry_id = entry_id

        self._footnote_ofs = counter.footnote
        self._footnote_buffer = footnote_buffer

        self._toc_buffer = toc_buffer

        self._counter = counter

    def _inner(self, text):
        """ process some inner markdown """
        return misaka.Markdown(self,
                               self._config.get('markdown_extensions',
                                                config.markdown_extensions))(text)

    @staticmethod
    def footnotes(_):
        """ Stub function; footnote rendering is handled by
        :py:func:entry.entry.footnotes """
        return None

    def _footnote_num(self, num):
        return num + self._footnote_ofs

    def _footnote_id(self, num, anchor):
        return f'{anchor}_e{self._entry_id}_fn{self._footnote_num(num)}'

    def _footnote_url(self, num, anchor):
        return urllib.parse.urljoin(self._config.get('footnotes_link', ''),
                                    '#' + self._footnote_id(num, anchor))

    def footnote_ref(self, num):
        """ Render a link to a footnote

        Relevant configuration options:
        * ``footnotes_class``: The class to apply to a footnote marker
        * ``footnotes_link``: The base URL for footnote links
        """

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
        """ Renders the body of a footnote to be used by :py:func:`entry.Entry.footnotes`.

        Relevant configuration options:

        * ``footnotes_link``: The base URL for footnote links
        * ``footnotes_return``: The return symbol on an expanded footnote
          (default: ``'↩'``)
        """

        LOGGER.debug("footnote_def %d: %s", num, content)

        self._counter.footnote_def(content, num)

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
        """ Return a reasonable anchor ID for a heading."""
        return '{eid}_h{level}_{num}_{slug}'.format(
            eid=self._entry_id,
            level=level,
            num=num,
            slug=slugify.slugify(content, max_length=32))

    def header(self, content, level):
        """ Make a header with anchor.

        Relevant configuration:

        * ``toc_link``: The base URL for table of contents links from a heading
        * ``heading_link_class``: The class to apply to a TOC link from a heading
        * ``heading_link_attrs``: Additional attributes to apply to TOC links from headings
        * ``heading_template``: The format template for a heading's TOC link
          (default: ``{link}</a>{{text}}``). Receives the following template arguments:
            * ``{link}``: The ``<a>`` tag linking to the TOC entry
            * ``{text}``: The text of the heading
         """

        self._counter.header(content, level)
        htag = f'h{level}'

        hid = self._header_id(html_entry.strip_html(content,
                                                    remove_elements=PLAINTEXT_REMOVE_ELEMENTS),
                              level, self._counter.toc)

        atag = utils.make_tag('a', {
            'href': urllib.parse.urljoin(self._config.get('toc_link', ''),
                                         '#' + hid),
            'class': self._config.get('heading_link_class', False),
            **self._config.get('heading_link_attrs', {})
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

        Extended syntax::

            ![alt text{container_args}](image1.jpg{img_args} "title text"
            |image2.jpg{img_args} "title text"
            |...)

        Configuration for each image comes from the page template, then from the
        ``container_args``, then from the ``img_args``.

        Configuration that applies to the image set itself:

        * ``figure``: If set, wrap the image set in a ``<figure>`` tag. If this
          value is a string, use the string value as the CSS class name.

        * ``caption``: If set, add the text as a ``<figcaption>``. Markdown supported.
          Implies ``figure=True``.

        * ``div_class``: The CSS class name to use on any wrapper div

        * ``div_style``: Additional CSS styles to apply to the wrapper div

        * ``count``: The maximum number of images to show at once

        * ``more_text``: If there are more than ``count`` images, add this text
          indicating that there are more images to be seen. This string gets two template
          arguments, ``{count}`` which is the total number of images in the set, and
          ``{remain}`` which is the number of images omitted from the set.

        * ``more_link``: If `more_text` is shown, this will format the text as a link
          to this location.

        * ``more_class``: If `more_text` is shown, applies this CSS class to the link

        See :py:mod:`publ.image` for configuration for image renditions.

        """
        # pylint: disable=too-many-locals

        # If we aren't generating images or markup, there's no reason to do any of this
        if self._config.get('_suppress_images') or not self._config.get('markup', True):
            return ' '

        text = ''

        image_specs = raw_url
        if title:
            image_specs += f' "{title}"'

        alt, container_args = image.parse_img_config(alt)

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
                    a=utils.make_tag('a', {
                        'href': container_args['more_link'],
                        'class': container_args.get('more_class', False)
                    }))
            text += flask.Markup(more_text)

        if text and (container_args.get('div_class') or
                     container_args.get('div_style')):
            text = '{tag}{text}</div>'.format(
                tag=utils.make_tag('div',
                                   {'class': container_args.get('div_class') or False,
                                    'style': container_args.get('div_style') or False}),
                text=text)

        if text and (container_args.get('figure') or container_args.get('caption')):
            fig_class = container_args.get('figure')
            if container_args.get('caption'):
                caption = '<figcaption>' + utils.strip_single_paragraph(
                    self._inner(container_args['caption'])) + '</figcaption>'
            else:
                caption = ''
            text = '{tag}{text}{caption}</figure>'.format(
                tag=utils.make_tag('figure',
                                   {'class': fig_class if isinstance(fig_class, str) else False}),
                text=text,
                caption=caption)

        # if text is ''/falsy then misaka interprets this as a failed parse...
        return text or ' '

    def blockcode(self, text, lang):
        """ Pass a code fence through pygments, and add line-numbering scaffolding.

        Relevant configuration:

        * ``code_highlight``: Whether to apply syntax highlighting to fenced
          code blocks (default: ``True``)
        * ``code_number_links``: Whether to add line-numbering links to fenced
          code blocks' lines. If set to a string, specifies the base URL for
          these links (default: ``True``)

        """
        LOGGER.debug("blockcode lang=%s", lang)

        self._counter.blockcode(text, lang)

        out = '<figure class="blockcode">'

        lang, _, args = utils.parse_spec(lang, 0)
        if args:
            args = {**self._config, **args}
        else:
            args = self._config
        LOGGER.debug("Code: language=%s args=%s", lang, args)

        if text.startswith('!'):
            caption, _, text = text.partition('\n')
            caption = self._inner(caption[1:]).strip()
            if caption:
                out += '<figcaption>' + utils.strip_single_paragraph(caption) + '</figcaption>'
        elif text.startswith(r'\!') or text.startswith('\n'):
            # Allow the initial ! to be escaped out, or skip an initial blank line
            text = text[1:]

        highlight = lang and args.get('code_highlight', True)
        number_lines = highlight and args.get('code_number_links', True)

        if highlight:
            try:
                lexer = pygments.lexers.get_lexer_by_name(lang or 'text', stripall=True)
            except pygments.lexers.ClassNotFound:
                lexer = pygments.lexers.TextLexer()  # pylint:disable=no-member
        else:
            lexer = None

        out += utils.make_tag('pre', {
            'class': 'highlight' if highlight else False,
            'data-language': lang if lang else False,
            'data-line-numbers': None if number_lines else False,
        } if lang else {})

        if lexer:
            link_base = number_lines
            if link_base is True:
                # It was set explicitly True, which means we need to re-inherit the
                # default from the template
                link_base = self._config.get('code_number_links')
            formatter = HtmlCodeFormatter(
                line_id_prefix=f"e{self._entry_id}cb{self._counter.code_blocks}",
                link_base=link_base,
            )
            out += pygments.highlight(str(text), lexer, formatter)
        else:
            lines = text.splitlines()
            for line in lines:
                out += ('<span class="line"><span class="line-content">'
                        + html.escape(line) + '</span></span>\n')

        out += '</pre></figure>'

        return out

    def link(self, content, link, title=''):
        """ Emit a link, potentially remapped based on our embed or static rules.

        Relevant configuration:

        * ``absolute``: Whether to produce absolute/external, rather than relative,
          links (default: ``False``)
        """

        if not self._config.get('markup', True):
            return content

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
        """ emit a paragraph """

        # if the content contains a top-level block element then don't wrap it in a <p>
        # tag
        for element in ('div', 'figure'):
            if content.startswith(f'<{element}') and content.endswith(f'</{element}>'):
                return '\n' + content + '\n'

        return '<p>' + content + '</p>'

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


def to_html(text, args, search_path,
            counter: ItemCounter,
            entry_id: typing.Optional[int] = None,
            toc_buffer: typing.Optional[TocBuffer] = None,
            footnote_buffer: typing.Optional[typing.List[str]] = None,
            postprocess: bool = True):
    """ Convert Markdown text to HTML.

    toc_buffer -- a list of (level,text) for all headings in the entry

    footnote_buffer -- a list that will contain <li>s with the footnote items, if
    there are any footnotes to be found.

    postprocess -- whether to postprocess the buffers for smartypants/HTML/etc.
    """
    # pylint:disable=too-many-arguments

    LOGGER.debug("counter: %s %s", id(counter), counter)

    footnotes: typing.List[str] = footnote_buffer if footnote_buffer is not None else []
    tocs: TocBuffer = toc_buffer if toc_buffer is not None else []

    # first process as Markdown
    renderer = HtmlRenderer({**config.layout, **args},
                            search_path,
                            toc_buffer=tocs,
                            footnote_buffer=footnotes,
                            entry_id=entry_id,
                            counter=counter)
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
        super().__init__({}, [], entry_id=0, toc_buffer=[], footnote_buffer=[],
                         counter=ItemCounter())

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

    def header(self, content, level):
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

    if smartquotes:
        text = misaka.smartypants(text)

    if markup:
        return flask.Markup(text)

    return html_entry.strip_html(text, remove_elements=PLAINTEXT_REMOVE_ELEMENTS)


def toc_to_html(toc: TocBuffer, max_level: Optional[int] = None) -> str:
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
