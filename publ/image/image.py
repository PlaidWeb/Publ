""" Base class for managed images """

import html
import typing
from abc import ABC, abstractmethod
from typing import Optional

import flask

from .. import utils

ImgSize = typing.Tuple[int, int]
RenditionAttrs = typing.Dict[str, typing.Any]


class Image(ABC):
    """ Base class for image handlers """

    def __init__(self, search_path):
        self.search_path = search_path

    @abstractmethod
    def _key(self):
        pass

    def __repr__(self):
        return repr((self._key(), repr(self.search_path)))

    def __hash__(self):
        return hash((self._key(), repr(self.search_path)))

    @abstractmethod
    def get_rendition(self, output_scale: int = 1, **kwargs) -> typing.Tuple[str, ImgSize]:
        """ Get a rendition of the image with the specified output scale and specification.

        Returns: a tuple of (url, size) for the image. """

    @abstractmethod
    def _get_img_attrs(self,
                       spec: utils.ArgDict,
                       style_parts: typing.List[str]) -> utils.TagAttrs:
        """ Get the img attributes for the given rendition arguments. Style parts
        should be appended to the style_parts instead.
        """

    @property
    @abstractmethod
    def _filename(self) -> str:
        """ Get the filename of the file, for default alt text purposes """

    def get_img_attrs(self, params: dict) -> utils.TagAttrs:
        """ Get an attribute list (src, style, et al) for the image.

        Returns: a dict of attributes e.g. {'src':'foo.jpg','srcset':'foo.jpg 1x, bar.jpg 2x']
        """

        params = utils.prefix_normalize(params)

        styles: typing.List[str] = []
        attrs = self._get_img_attrs(params, styles)

        attrs['loading'] = params.get('image_loading', 'lazy')

        for key in ('img_style', 'style'):
            styles += utils.as_list(params.get(key))

        shape = self._get_shape_style(params)
        if shape:
            styles.append(f"shape-outside: url('{shape}')")

        def set_val(key, val):
            if val is not None:
                attrs[key] = val

        if 'img_class' in params or 'class' in params:
            set_val('class', params.get('img_class', params.get('class')))
        if 'img_id' in params or 'id' in params:
            set_val('id', params.get('img_id', params.get('id')))
        if styles:
            set_val('style', ';'.join(styles))

        if '_mark_rewritten' in params:
            set_val('data-publ-rewritten', params['_mark_rewritten'])

        return attrs

    def get_img_tag(self,
                    title: Optional[str] = None,
                    alt_text: Optional[str] = None,
                    _show_thumbnail: bool = True,
                    **kwargs) -> str:
        """ Build a <img> tag for the image with the specified options.

        Returns: an HTML fragment. """

        try:
            attrs = self.get_img_attrs(kwargs)

            if alt_text:
                attrs['alt'] = alt_text
            else:
                attrs['alt'] = self._filename

            if title:
                attrs['title'] = title

            if _show_thumbnail:
                thumb = utils.make_tag(
                    'img', attrs, start_end=kwargs.get('xhtml', False))
            else:
                thumb = ''

            return flask.Markup(
                self._wrap_link_target(
                    kwargs,
                    thumb,
                    title))
        except FileNotFoundError as error:
            text = '<span class="error">Image not found: '
            text += f'<code>{html.escape(error.filename)}</code>'
            if ' ' in error.filename:
                text += ' (Did you forget a <code>|</code>?)'
            text += '</span>'
            return flask.Markup(text)

    def _get_shape_style(self, kwargs):
        shape = kwargs.get('shape')
        if not shape:
            return None

        # Only pull in size-related attributes (e.g. no format, background,
        # etc.)
        size_args = {k: v for k, v in kwargs.items() if k in (
            'width', 'height', 'max_width', 'max_height', 'absolute', 'crop'
        )}

        if shape is True:
            # if the shape is True, just return the base rendition
            url, _ = self.get_rendition(1, **size_args)
        else:
            # otherwise, the usual rules apply
            from . import get_image  # pylint: disable=cyclic-import
            other_image = get_image(shape, self.search_path)
            url, _ = other_image.get_rendition(1, **size_args)
        return url

    def get_css_background(self, uncomment: bool = False, **kwargs):
        """ Get the CSS background attributes for an element.

        Additional arguments:

        uncomment -- surround the attributes with `*/` and `/*` so that the
            template tag can be kept inside a comment block, to keep syntax
            highlighters happy
        """

        text = self._css_background(**kwargs)
        if uncomment:
            text = f' */ {text} /* '

        return text

    @abstractmethod
    def _css_background(self, **kwargs):
        """ Build CSS background-image properties that apply this image.

        Returns: a CSS fragment. """

    def __call__(self, *args, **kwargs):
        url, _ = self.get_rendition(*args, **kwargs)
        return url

    def __str__(self):
        return self()

    def _wrap_link_target(self, kwargs,
                          text: str,
                          title: typing.Optional[str]) -> str:
        if kwargs.get('link') is not None:
            if not text or kwargs['link'] is False:
                return text

            # pylint:disable=consider-using-f-string
            return '{}{}</a>'.format(
                utils.make_tag(
                    'a', {
                        'href': utils.remap_link_target(
                            kwargs['link'],
                            kwargs.get('absolute')),
                        'class': kwargs.get('link_class', False)
                    }),
                text)

        if kwargs.get('gallery_id'):
            return f'{self._fullsize_link_tag(kwargs, title)}{text}</a>'

        return text

    def get_fullsize(self, kwargs) -> str:
        """ Get the fullsize rendition URL """
        fullsize_args = {}

        if 'absolute' in kwargs:
            fullsize_args['absolute'] = kwargs['absolute']

        for key in ('width', 'height', 'quality', 'format', 'background', 'crop'):
            fsk = 'fullsize_' + key
            if fsk in kwargs:
                fullsize_args[key] = kwargs[fsk]

        img_fullsize, _ = self.get_rendition(1, **fullsize_args)
        return img_fullsize

    def _fullsize_link_tag(self, kwargs, title: typing.Optional[str]) -> str:
        """ Render an <a href> that points to the fullsize rendition specified """

        return utils.make_tag('a', {
            'href': self.get_fullsize(kwargs),
            'data-lightbox': kwargs.get('gallery_id', False),
            'title': title or False,
            'class': kwargs.get('link_class', False)
        })
