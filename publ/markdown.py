# markdown.py
""" handler for markdown formatting """

import re
import ast

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

        alt, container_args = self._parse_alt_text(alt)

        spec_list = image_specs.split('|')

        container_args = {**self._config, **container_args}

        container_class = container_args.get('container_class')
        if container_class:
            text += '<div class="{}">'.format(flask.escape(container_class))

        absolute = self._config.get('absolute')

        for spec in spec_list:
            path, image_args, title = self._parse_image_spec(spec.strip())

            img = image.get_image(path, self._image_search_path)
            if not img:
                text += '<span class="error">Couldn\'t find image: {}</span>'.format(
                    flask.escape(path))
                continue

            image_args = {**container_args, **image_args}

            rendition_args = self._build_rendition_args(image_args)
            img_1x, width, height = img.get_rendition(1, rendition_args)
            img_2x, _, _ = img.get_rendition(2, rendition_args)

            img_1x = utils.static_url(img_1x, absolute)
            img_2x = utils.static_url(img_2x, absolute)

            text += '<img src="{}"'.format(img_1x)
            if img_1x != img_2x:
                text += ' srcset="{} 1x, {} 2x"'.format(img_1x, img_2x)

            if width:
                text += ' width="{}"'.format(width)
            if height:
                text += ' height="{}"'.format(height)

            if alt:
                text += ' alt="{}"'.format(flask.escape(alt))
            if title:
                text += ' title="{}"'.format(flask.escape(title))

            text += '</img>'

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

    @staticmethod
    def _build_rendition_args(args):
        return {
            'max_width': args.get('force_width', args.get('width')),
            'max_height': args.get('force_height', args.get('height')),
            'input_scale': args.get('scale'),
            'scale_min_width': args.get('scale_min_width'),
            'scale_min_height': args.get('scale_min_height')
        }


def to_html(text, search_path, config):
    """ Convert Markdown text to HTML """

    processor = misaka.Markdown(HtmlRenderer(config, search_path),
                                extensions=ENABLED_EXTENSIONS)
    return processor(text)
