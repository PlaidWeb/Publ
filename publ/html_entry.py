# html_entry.py
""" HTML entry processing functionality """

import misaka
import flask

from . import utils, links, image


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
                    or (key.lower() == 'src' and not tag.lower() == 'img')):
                out_attrs.append((key, links.remap_path(
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

        for key, val in attrs:
            if key.lower() == 'width' or key.lower() == 'height':
                try:
                    config[key.lower()] = int(val)
                except ValueError:
                    pass
            elif key.lower() == 'src':
                path = val

        img_path, img_args, _ = image.parse_image_spec(path)
        img = image.get_image(img_path, self._search_path)

        for key, val in img_args.items():
            if val and key not in config:
                config[key] = val

        try:
            img_attrs = img.get_img_attrs(**config)
        except FileNotFoundError as error:
            return [('data-publ-error', 'file not found: {}'.format(error.filename))]

        # return the original attr list with the computed overrides in place
        return [(key, val) for key, val in attrs
                if key.lower() not in img_attrs] + list(img_attrs.items())


def process(text, config, search_path):
    """ Process an HTML entry's HTML """
    processor = HTMLEntry(config, search_path)
    processor.feed(text)
    text = processor.get_data()

    if not config.get('no_smartquotes'):
        text = misaka.smartypants(text)

    return flask.Markup(text)
