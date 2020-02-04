# html_entry.py
""" HTML entry processing functionality """

import logging
import typing

import flask

from . import image, links, utils

LOGGER = logging.getLogger(__name__)


class HTMLEntry(utils.HTMLTransform):
    """ An HTML manipulator to fixup src and href attributes """

    def __init__(self, config, search_path):
        super().__init__()

        self._search_path = search_path
        self._config = config

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
        config = {**self._config}
        is_rewritten = False

        for key, val in attrs:
            if key.lower() == 'width' or key.lower() == 'height':
                try:
                    config[key.lower()] = int(val)
                except ValueError:
                    pass
            elif key.lower() == 'src':
                path = val
            elif key == 'data-publ-rewritten':
                is_rewritten = True

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

        for key, val in img_args.items():
            if val and key not in config:
                config[key] = val

        try:
            img_attrs = img.get_img_attrs(**config)
        except FileNotFoundError as error:
            img_attrs = {
                'data-publ-error': 'File Not Found: {}'.format(error.filename)
            }
        except Exception as error:  # pylint:disable=broad-except
            LOGGER.exception("Got exception: %s", error)
            img_attrs = {
                'data-publ-error': 'Error: {}'.format(str(error))
            }

        # return the original attr list with the computed overrides in place
        return [(key, val) for key, val in attrs
                if key.lower() not in img_attrs] + list(img_attrs.items())


def process(text, config, search_path):
    """ Process an HTML entry's HTML """
    processor = HTMLEntry(config, search_path)
    processor.feed(text)
    text = processor.get_data()

    if not config.get('markup', True):
        text = strip_html(text)

    return flask.Markup(text)


class HTMLStripper(utils.HTMLTransform):
    """ Strip all HTML tags from a document, except those which are allowed """

    def __init__(self,
                 allowed_tags: typing.Tuple[str] = None,
                 allowed_attrs: typing.Tuple[str] = None):
        super().__init__()
        self._allowed_tags = allowed_tags
        self._allowed_attrs = allowed_attrs

    def _filter(self, tag, attrs, **kwargs) -> str:
        if self._allowed_tags and tag in self._allowed_tags:
            return utils.make_tag(tag,
                                  {key: val
                                   for key, val in attrs
                                   if self._allowed_attrs
                                   and key in self._allowed_attrs},
                                  **kwargs)
        return ''

    def handle_starttag(self, tag, attrs):
        self.append(self._filter(tag, attrs))

    def handle_endtag(self, tag):
        if self._allowed_tags and tag in self._allowed_tags:
            self.append('</{tag}>'.format(tag=tag))

    def handle_startendtag(self, tag, attrs):
        self.append(self._filter(tag, attrs, start_end=True))

    def handle_data(self, data):
        self.append(data)


def strip_html(text,
               allowed_tags: typing.Tuple[str] = None,
               allowed_attrs: typing.Tuple[str] = None) -> str:
    """ Strip all HTML formatting off of a chunk of text """
    strip = HTMLStripper(allowed_tags, allowed_attrs)
    strip.feed(text)
    return strip.get_data()
