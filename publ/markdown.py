# markdown.py
""" handler for markdown formatting """

import re
import ast
import os

import misaka
import flask

import pygments
import pygments.formatters
import pygments.lexers

from . import image, utils

ENABLED_EXTENSIONS = [
    'fenced-code', 'footnotes', 'strikethrough', 'highlight', 'math', 'math-explicit'
]


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

        limit = self._config.get('limit')
        if limit:
            spec_list = spec_list[:limit]

        container_args = {**self._config, **container_args}

        container_class = container_args.get('container_class')
        if container_class:
            text += '<div class="{}">'.format(flask.escape(container_class))

        for spec in spec_list:
            if not spec:
                continue

            text += self._render_image(spec, container_args, alt)

        if container_class:
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

            # remote images should only use their direct configuration
            if path.startswith('//') or '://' in path:
                return self._remote_image(path, image_args, title, alt_text)

            composite_args = {**container_args, **image_args}
            return self._local_image(path, composite_args, title, alt_text)
        except Exception as err:  # pylint: disable=broad-except
            return ('<span class="error">Couldn\'t parse image spec: ' +
                    '<code>{}</code> {}</span>'.format(flask.escape(spec),
                                                       flask.escape(str(err))))

    def _local_image(self, path, image_args, title, alt_text):
        """ Render an img tag for a locally-stored image """

        if os.path.isabs(path):
            search_path = self._absolute_search_path
            path = os.path.relpath(path, "/")
        else:
            search_path = self._relative_search_path

        img = image.get_image(path, search_path)
        if not img:
            return ('<span class="error">Couldn\'t find image: ' +
                    '<code>{}</code></span>'.format(flask.escape(path)))

        img_1x, width, height = img.get_rendition(1, image_args)
        img_2x, _, _ = img.get_rendition(2, image_args)

        absolute = self._config.get('absolute')

        img_1x = utils.static_url(img_1x, absolute)
        img_2x = utils.static_url(img_2x, absolute)

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
        return text

    @staticmethod
    def _remote_image(path, image_args, title, alt_text):
        """ Render an img tag for a remotely-stored image """

        text = '<img src="{}"'.format(path)

        if 'width' in image_args:
            text += ' width="{}"'.format(image_args['width'])
        if 'height' in image_args:
            text += ' height="{}"'.format(image_args['height'])

        if title:
            text += ' title="{}"'.format(flask.escape(title))
        if alt_text:
            text += ' alt="{}"'.format(flask.escape(alt_text))

        text += '>'
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
