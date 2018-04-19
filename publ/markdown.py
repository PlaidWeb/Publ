# markdown.py
""" handler for markdown formatting """

from __future__ import absolute_import

import re
import ast
import os
import logging

import misaka
import flask

import pygments
import pygments.formatters
import pygments.lexers

from . import image, utils

ENABLED_EXTENSIONS = [
    'fenced-code', 'footnotes', 'strikethrough', 'highlight', 'math', 'math-explicit'
]

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


class HtmlRenderer(misaka.HtmlRenderer):
    """ Customized renderer for enhancing Markdown formatting """

    def __init__(self, config):
        super().__init__()
        self._config = config
        self._relative_search_path = config.get(
            'relative_search_path', config.get('search_path'))
        self._absolute_search_path = config.get(
            'absolute_search_path', config.get('search_path'))

    def image(self, raw_url, title='', alt=''):
        """ Adapt a standard Markdown image to a generated rendition """
        # pylint: disable=too-many-locals

        text = ''

        image_specs = raw_url
        if title:
            image_specs += ' "{}"'.format(title)

        alt, container_args = self._parse_alt_text(alt)

        spec_list = [spec.strip() for spec in image_specs.split('|')]

        if 'first' in self._config:
            spec_list = spec_list[self._config['first']]
        if 'limit' in self._config:
            spec_list = spec_list[:self._config['limit']]

        container_args = {**self._config, **container_args}

        if 'container_class' in container_args:
            text += '<div class="{}">'.format(
                flask.escape(container_args['container_class']))

        for spec in spec_list:
            if not spec:
                continue

            text += self._render_image(spec,
                                       container_args,
                                       alt) if spec else ''

        if 'container_class' in container_args:
            text += '</div>'

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

    def _render_image(self, spec, container_args, alt_text=None):
        """ Render an image specification into an <img> tag """

        try:
            path, image_args, title = self._parse_image_spec(spec)
            composite_args = {**container_args, **image_args}

            if path.startswith('//') or '://' in path:
                return self._remote_image(path, composite_args, title, alt_text)

            return self._local_image(path, composite_args, title, alt_text)
        except Exception as err:  # pylint: disable=broad-except
            logger.exception("Got error on spec %s: %s", spec, err)
            return ('<span class="error">Couldn\'t parse image spec: ' +
                    '<code>{}</code> {}</span>'.format(flask.escape(spec),
                                                       flask.escape(str(err))))

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
        # pylint: disable=too-many-locals,too-many-branches

        # Determine the appropriate search path for the image request
        if os.path.isabs(path):
            search_path = self._absolute_search_path
            path = os.path.relpath(path, "/")
        else:
            search_path = self._relative_search_path

        # Get the image object
        img = image.get_image(path, search_path)
        if not img:
            return ('<span class="error">Couldn\'t find image: ' +
                    '<code>{}</code></span>'.format(flask.escape(path)))

        # Get the 1x and 2x renditions
        img_1x, width, height = img.get_rendition(
            1, self._rendition_args(image_args, {"quality": "quality_ldpi"}))
        img_2x, _, _ = img.get_rendition(
            2, self._rendition_args(image_args, {"quality": "quality_hdpi"}))

        # ... and their URLs
        absolute = self._config.get('absolute')
        img_1x = utils.static_url(img_1x, absolute)
        img_2x = utils.static_url(img_2x, absolute)

        # Build the <img> tag
        text = '<img src="{}"'.format(img_1x)
        if img_1x != img_2x:
            text += ' srcset="{} 1x, {} 2x"'.format(img_1x, img_2x)

        if width:
            text += ' width="{}"'.format(width)
        if height:
            text += ' height="{}"'.format(height)

        if alt_text:
            text += ' alt="{}"'.format(flask.escape(alt_text))
        if title:
            text += ' title="{}"'.format(flask.escape(title))

        text += '>'

        # Wrap it in a link as appropriate
        if 'link' in image_args:
            text = '<a href="{}">{}</a>'.format(
                flask.escape(image_args['link']), text)
        elif 'gallery_id' in image_args:
            fullsize_args = {}
            for key in ['width', 'height', 'quality', 'format', 'background']:
                fsk = 'fullsize_' + key
                if fsk in image_args:
                    fullsize_args[key] = image_args[fsk]

            img_fullsize, _, _ = img.get_rendition(1, fullsize_args)
            img_fullsize = utils.static_url(img_fullsize, absolute)

            link = '<a data-lightbox="{}" href="{}"'.format(
                flask.escape(image_args['gallery_id']), img_fullsize)
            if title:
                link += ' title="{}"'.format(flask.escape(title))
            link += '>'
            text = link + text + '</a>'

        return text

    @staticmethod
    def _remote_image(path, image_args, title, alt_text):
        """ Render an img tag for a remotely-stored image """

        text = '<img src="{}"'.format(path)

        if 'width' in image_args:
            text += ' width="{}"'.format(image_args['width'])
        elif 'height' in image_args:
            text += ' height="{}"'.format(image_args['height'])

        if title:
            text += ' title="{}"'.format(flask.escape(title))
        if alt_text:
            text += ' alt="{}"'.format(flask.escape(alt_text))

        text += '>'

        if 'link' in image_args:
            text = '<a href="{}">{}</a>'.format(
                flask.escape(image_args['link']), text)
        elif 'gallery_id' in image_args:
            text = '<a data-lightbox="{}" href="{}">{}</a>'.format(
                flask.escape(image_args['gallery_id']),
                flask.escape(path),
                text)

        return text

    def _parse_image_spec(self, spec):
        """ Parse an image spec out into (path,args,title) """

        # I was having trouble coming up with a single RE that did it right,
        # so let's just break it down into sub-problems. First, parse out the
        # alt text...
        match = re.match(r'([^\"]+)\s+\"(.*)\"$', spec)
        if match:
            spec, title = match.group(1, 2)
        else:
            title = None

        # and now parse out the arglist
        match = re.match(r'([^\{]*)(\{(.*)\})$', spec)
        if match:
            spec = match.group(1)
            args = self._parse_args(match.group(3))
        else:
            args = {}

        return spec, args, title

    def _parse_alt_text(self, spec):
        """ Parse the alt text out into (alt_text,args) """
        match = re.match(r'([^\{]*)(\{(.*)\})$', spec)
        if match:
            spec = match.group(1)
            args = self._parse_args(match.group(3))
        else:
            args = {}

        return spec, args

    @staticmethod
    def _parse_args(args):
        """ Parse an arglist into args and kwargs """
        # per https://stackoverflow.com/a/49723227/318857

        def extract_value(node):
            """ extract a value from the AST """
            if isinstance(node, ast.Str):
                return node.s
            elif isinstance(node, ast.Num):
                return node.n
            else:
                raise TypeError('node type not supported: {}'.format(node))

        args = 'f({})'.format(args)
        tree = ast.parse(args)
        funccall = tree.body[0].value

        args = [extract_value(arg) for arg in funccall.args]
        kwargs = {arg.arg: extract_value(arg.value)
                  for arg in funccall.keywords}

        if len(args) > 2:
            raise TypeError(
                "Expected at most 2 positional args but {} were given".format(len(args)))

        if len(args) >= 1:
            kwargs['width'] = int(args[0])
        if len(args) >= 2:
            kwargs['height'] = int(args[1])

        return kwargs


def to_html(text, config):
    """ Convert Markdown text to HTML """

    processor = misaka.Markdown(HtmlRenderer(config),
                                extensions=ENABLED_EXTENSIONS)
    return processor(text)
