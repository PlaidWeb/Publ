# html_entry.py
""" HTML entry processing functionality """

import html.parser

import misaka
import flask

from . import utils
from . import image


class HTMLEntry(html.parser.HTMLParser):
    """ An HTML manipulator to fixup src and href attributes """

    def __init__(self, config, search_path):
        super().__init__()

        self._search_path = search_path
        self._config = config

        self.reset()
        self.strict = False
        self.convert_charrefs = False
        self.fed = []

    def handle_data(self, data):
        """ Simply append the text data """
        self.fed.append(data)

    def get_data(self):
        """ Concatenate the output """
        return ''.join(self.fed)

    def handle_starttag(self, tag, attrs):
        """ Handle a start tag """
        self._handle_tag(tag, attrs, False)

    def handle_endtag(self, tag):
        """ Handle an end tag """
        self.fed.append('</' + tag + '>')

    def handle_startendtag(self, tag, attrs):
        """ Handle a self-closing tag """
        self._handle_tag(tag, attrs, True)

    def error(self, message):
        """ Deprecated, per https://bugs.python.org/issue31844 """
        return message

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
            if key.lower() == 'href':
                out_attrs.append((key, self._remap_path(val)))
            else:
                out_attrs.append((key, val))

        self.fed.append(
            utils.make_tag(
                tag,
                out_attrs,
                self_closing))

    def _image_attrs(self, attrs):
        """ Rewrite the SRC attribute on an <img> tag, possibly adding a SRCSET.
        """

        path = None
        config = self._config

        for key, val in attrs:
            if key.lower() == 'width' or key.lower() == 'height':
                try:
                    config = {**config, key.lower(): int(val)}
                except ValueError:
                    pass
            elif key.lower() == 'src':
                path = val

        img = image.get_image(path, self._search_path)

        try:
            img_attrs = {k: v for k, v in img.get_img_attrs(**config)}
        except FileNotFoundError as error:
            return [('data-publ-error', 'file not found: {}'.format(error.filename))]

        return [(key, val) for key, val in attrs if key not in img_attrs] + list(img_attrs.items())

    def _remap_path(self, path):
        """ Remap a link target to an appropriate URL """

        # Remote or static URL: do the thing
        if not path.startswith('//') and not '://' in path:
            path, sep, anchor = path.partition('#')
            entry = utils.find_entry(path, self._search_path)
            if entry:
                return entry.link(self._config) + sep + anchor

        # Image URL: do the thing
        img_path, img_args, _ = image.parse_image_spec(path)
        img = image.get_image(img_path, self._search_path)
        if isinstance(img, image.LocalImage):
            path, _ = img.get_rendition(**img_args)

        return utils.remap_link_target(path, self._config.get('absolute'))


def process(text, config, search_path):
    processor = HTMLEntry(config, search_path)
    processor.feed(text)
    text = processor.get_data()

    if not config.get('no_smartquotes'):
        text = misaka.smartypants(text)

    return flask.Markup(text)
