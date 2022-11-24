# html_entry.py
""" HTML entry processing functionality """

import html
import logging
import re
import typing
from typing import Optional

import flask

from . import image, links, utils
from .config import config

LOGGER = logging.getLogger(__name__)


class HTMLEntry(utils.HTMLTransform):
    """ An HTML manipulator to fixup src and href attributes """

    def __init__(self, args, search_path):
        super().__init__()

        self._search_path = search_path
        self._config = args

    def handle_decl(self, decl):
        self.append('<!' + decl + '>')

    def handle_data(self, data):
        self.append(data)

    def handle_starttag(self, tag, attrs):
        """ Handle a start tag """
        self._handle_tag(tag, attrs, False)

    def handle_endtag(self, tag):
        """ Handle an end tag """
        self.append('</' + tag + '>')

    def handle_pi(self, data):
        LOGGER.warning("handle_pi: '%s'", data)

    def handle_comment(self, data):
        self.append('<!--' + data + '-->')

    def handle_startendtag(self, tag, attrs):
        """ Handle a self-closing tag """
        self._handle_tag(tag, attrs, True)

    def _handle_tag(self, tag, attrs, self_closing):
        """ Handle a tag.

        attrs -- the attributes of the tag
        self_closing -- whether this is self-closing
        """

        if tag.lower() == 'img':
            attrs = self._image_attrs(attrs)

        # Remap the attributes
        out_attrs = []
        for key, val in attrs:
            if (key.lower() == 'href'
                    or key.startswith('$')
                    or (key.lower() == 'src' and tag.lower() != 'img')):
                if key.startswith('$'):
                    key = key[1:]
                out_attrs.append((key, links.resolve(
                    val, self._search_path, self._config.get('absolute'))))
            else:
                out_attrs.append((key, val))

        self.append(
            utils.make_tag(
                tag,
                out_attrs,
                self_closing))

    def _image_attrs(self, attrs):
        """ Rewrite the SRC attribute on an <img> tag, possibly adding a SRCSET.
        """

        path = None
        attr_args = {}
        is_rewritten = False

        for key, val in attrs:
            if key.lower() == 'width' or key.lower() == 'height':
                try:
                    attr_args[key.lower()] = int(val)
                except ValueError:
                    pass
            elif key.lower() == 'src':
                path = val
            elif key == 'data-publ-rewritten':
                is_rewritten = True
                break

        if is_rewritten:
            # This img tag was already rewritten by a previous processor, so just
            # remove that attribute and return the tag's original attributes
            LOGGER.debug("Detected already-rewritten image; %s", attrs)
            return [(key, val) for key, val in attrs if key != 'data-publ-rewritten']

        if not path:
            # this img doesn't have a src attribute, so there's something unconventional going on
            return attrs

        img_path, img_args, _ = image.parse_image_spec(path)
        img = image.get_image(img_path, self._search_path)

        try:
            img_attrs = img.get_img_attrs({**self._config,
                                           **attr_args,
                                           **img_args})
        except FileNotFoundError as error:
            img_attrs = {
                'data-publ-error': f'File Not Found: {error.filename}'
            }
        except Exception as error:  # pylint:disable=broad-except
            LOGGER.exception("Got exception: %s", error)
            img_attrs = {
                'data-publ-error': f'Error: {error}'
            }

        # return the original attr list with the computed overrides in place
        return [(key, val) for key, val in attrs
                if key.lower() not in img_attrs] + list(img_attrs.items())


def process(text, args, search_path):
    """ Process an HTML entry's HTML """
    args = {**config.layout, **args}
    processor = HTMLEntry(args, search_path)
    processor.feed(text)
    text = processor.get_data()

    if not args.get('markup', True):
        text = strip_html(text)

    return flask.Markup(text)


class HTMLStripper(utils.HTMLTransform):
    """ Strip all HTML tags from a document, except those which are allowed """

    def __init__(self,
                 allowed_tags: Optional[typing.Iterable[str]] = None,
                 allowed_attrs: Optional[typing.Iterable[str]] = None,
                 remove_elements: Optional[typing.Iterable[str]] = None):
        super().__init__()
        self._allowed_tags = set(utils.as_list(allowed_tags))
        self._allowed_attrs = set(utils.as_list(allowed_attrs))
        self._remove_elements = set(utils.as_list(remove_elements))
        self._remove_depth = 0

    def _filter(self, tag, attrs, **kwargs) -> str:
        if self._allowed_tags and tag in self._allowed_tags:
            return utils.make_tag(tag,
                                  {key: val
                                   for key, val in attrs
                                   if key in self._allowed_attrs},
                                  **kwargs)
        if self._remove_elements and tag in self._remove_elements:
            self._remove_depth += 1
        return ''

    def handle_starttag(self, tag, attrs):
        self.append(self._filter(tag, attrs))

    def handle_endtag(self, tag):
        if self._allowed_tags and tag in self._allowed_tags:
            self.append(f'</{tag}>')
        elif self._remove_elements and tag in self._remove_elements:
            self._remove_depth -= 1

    def handle_startendtag(self, tag, attrs):
        self.append(self._filter(tag, attrs, start_end=True))

    def handle_data(self, data):
        if not self._remove_depth:
            self.append(data)


def strip_html(text,
               allowed_tags: Optional[typing.Iterable[str]] = None,
               allowed_attrs: Optional[typing.Iterable[str]] = None,
               remove_elements: Optional[typing.Iterable[str]] = None) -> str:
    """ Strip all HTML formatting off of a chunk of text """
    strip = HTMLStripper(allowed_tags, allowed_attrs, remove_elements)
    strip.feed(str(text))
    return re.sub(r' +', r' ', html.unescape(strip.get_data())).strip()


class FirstParagraph(utils.HTMLTransform):
    """ Get just the first paragraph out of an HTML document """

    def __init__(self):
        super().__init__()

        self._consume = True
        self._found = False

        self._tag_stack = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'table':
            self._consume = False

        if tag.lower() == 'p':
            if self._found:
                self._consume = False

        self._tag_stack.append(tag)

        if self._consume:
            self.append(utils.make_tag(tag, attrs))

    def handle_endtag(self, tag):
        while self._tag_stack and self._tag_stack.pop() != tag:
            pass

        if self._consume:
            self.append(f'</{tag}>')

        if tag.lower() == 'table' and not self._found:
            self._consume = True

        if (not self._tag_stack or tag.lower() == 'p') and self._found:
            self._consume = False

    def handle_startendtag(self, tag, attrs):
        if self._consume:
            self.append(utils.make_tag(tag, attrs, True))

    def handle_data(self, data):
        if self._consume and data.strip():
            self._found = True
            self.append(data)


def first_paragraph(text):
    """ Extract the first paragraph of text from an HTML document """
    first_para = FirstParagraph()
    first_para.feed(str(text))
    text = first_para.get_data()
    return re.sub(r'<p> *</p>', r'', text)
