# html_entry.py
""" HTML entry processing functionality """

import logging

import flask

from . import utils, links, image

LOGGER = logging.getLogger(__name__)


class HTMLEntry(utils.HTMLTransform):
    """ An HTML manipulator to fixup src and href attributes """

    def __init__(self, config, search_path):
        super().__init__()

        self._search_path = search_path
        self._config = config

    def handle_data(self, data):
        self.append(data)

    def handle_starttag(self, tag, attrs):
        """ Handle a start tag """
        self._handle_tag(tag, attrs, False)

    def handle_endtag(self, tag):
        """ Handle an end tag """
        self.append('</' + tag + '>')

    def handle_entityref(self, name):
        self.append('&' + name + ';')

    def handle_charref(self, name):
        self.append('&#' + name + ';')

    def handle_decl(self, decl):
        LOGGER.warning("handle_decl: '%s'", decl)

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
                    or (key.lower() == 'src' and tag.lower() != 'img')):
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

        img_path, img_args, _ = image.parse_image_spec(path)
        img = image.get_image(img_path, self._search_path)

        for key, val in img_args.items():
            if val and key not in config:
                config[key] = val

        try:
            img_attrs = img.get_img_attrs(**config)
        except FileNotFoundError as error:
            img_attrs = {
                'data-publ-error': 'file not found: {}'.format(error.filename)
            }

        # return the original attr list with the computed overrides in place
        return [(key, val) for key, val in attrs
                if key.lower() not in img_attrs] + list(img_attrs.items())


def process(text, config, search_path):
    """ Process an HTML entry's HTML """
    processor = HTMLEntry(config, search_path)
    processor.feed(text)
    text = processor.get_data()

    return flask.Markup(text)
