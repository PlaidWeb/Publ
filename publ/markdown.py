# markdown.py
""" handler for markdown formatting """

from __future__ import absolute_import

import logging
import urllib.parse

import misaka
import flask

import pygments
import pygments.formatters
import pygments.lexers

from . import image, utils

ENABLED_EXTENSIONS = [
    'fenced-code', 'footnotes', 'strikethrough', 'highlight', 'math', 'math-explicit'
]

CSS_SIZE_MODE = {
    'fit': 'contain',
    'fill': 'cover'
}

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
        absolute = self._config.get('absolute')

        if path.startswith('@'):
            # static resource
            return utils.static_url(path[1:], absolute=absolute)

        if absolute:
            # absolute-ify whatever the URL is
            return urllib.parse.urljoin(flask.request.url, path)

        return path

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

        if path.startswith('//') or path.startswith('@') or '://' in path:
            return self._remote_image(self._remap_path(path), composite_args, title, alt_text)

        return self._local_image(path, composite_args, title, alt_text)

    @staticmethod
    def _rendition_args(image_args, remap):
        """ Generate rendition arguments specific to a rendition. The 'remap'
        dict maps from destination key -> priority list of source keys
        """
        out_args = image_args
        for dest_key, src_keys in remap.items():
            remap_value = None
            if isinstance(src_keys, str):
                src_keys = [src_keys]

            for key in src_keys:
                if key in image_args:
                    remap_value = image_args[key]
                    break

            if remap_value is not None:
                if out_args is image_args:
                    out_args = {**image_args}
                out_args[dest_key] = remap_value

        return out_args

    def _local_image(self, path, image_args, title, alt_text):
        """ Render an img tag for a locally-stored image """

        # Get the image object
        img = image.get_image(path, self._image_search_path)
        if not img:
            return ('<span class="error">Couldn\'t find image: ' +
                    '<code>{}</code></span>'.format(flask.escape(path)))

        # Get the 1x and 2x renditions
        img_1x, size = img.get_rendition(
            1, self._rendition_args(image_args, {"quality": "quality_ldpi"}))
        img_2x, _ = img.get_rendition(
            2, self._rendition_args(image_args, {"quality": "quality_hdpi"}))

        # ... and their URLs
        absolute = self._config.get('absolute')
        img_1x = utils.static_url(img_1x, absolute)
        img_2x = utils.static_url(img_2x, absolute)

        text = utils.make_tag('img', {
            'src': img_1x,
            'width': size[0],
            'height': size[1],
            'srcset': "{} 1x, {} 2x".format(img_1x, img_2x) if img_1x != img_2x else None,
            'title': title,
            'alt': alt_text
        })

        # Wrap it in a link as appropriate
        if 'link' in image_args and image_args['link'] is not None:
            text = '<a href="{}">{}</a>'.format(
                flask.escape(image_args['link']), text)
        elif 'gallery_id' in image_args and image_args['gallery_id'] is not None:
            text = '{}{}</a>'.format(
                self._fullsize_link(
                    img, image_args, title, absolute),
                text)

        return text

    @staticmethod
    def _fullsize_link(img, image_args, title, absolute):
        fullsize_args = {}
        for key in ['width', 'height', 'quality', 'format', 'background']:
            fsk = 'fullsize_' + key
            if fsk in image_args:
                fullsize_args[key] = image_args[fsk]

        img_fullsize, _ = img.get_rendition(1, fullsize_args)
        img_fullsize = utils.static_url(img_fullsize, absolute)

        return utils.make_tag('a', {
            'href': img_fullsize,
            'data-lightbox': image_args['gallery_id'],
            'title': title
        })

    @staticmethod
    def _remote_image(path, image_args, title, alt_text):
        """ Render an img tag for a remotely-stored image """

        attrs = {
            'title': title,
            'alt': alt_text
        }

        # try to fudge the sizing
        width = image_args.get('width')
        height = image_args.get('height')
        size_mode = image_args.get('resize', 'fit')

        if width and height and size_mode != 'stretch':
            attrs['style'] = ';'.join([
                'background-image:url(\'{}\')'.format(flask.escape(path)),
                'background-size:{}'.format(CSS_SIZE_MODE[size_mode]),
                'background-position:{:.1f}% {:.1f}%'.format(
                    image_args.get('fill_crop_x', 0.5) * 100,
                    image_args.get('fill_crop_y', 0.5) * 100),
                'background-repeat:no-repeat'
            ])
            attrs['src'] = (
                'data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw'
            )
        else:
            attrs['src'] = path

        attrs['width'] = width
        attrs['height'] = height

        text = utils.make_tag('img', attrs)

        if 'link' in image_args and image_args['link'] is not None:
            text = '<a href="{}">{}</a>'.format(
                flask.escape(image_args['link']), text)
        elif 'gallery_id' in image_args and image_args['gallery_id'] is not None:
            text = '{}{}</a>'.format(
                utils.make_tag('a', {
                    'href': path,
                    'data-lightbox': image_args['gallery_id'],
                    'title': title
                }),
                text)

        return text


def to_html(text, config, image_search_path):
    """ Convert Markdown text to HTML """

    processor = misaka.Markdown(HtmlRenderer(config, image_search_path),
                                extensions=ENABLED_EXTENSIONS)
    return processor(text)
