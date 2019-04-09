""" Base class for managed images """

from abc import ABC, abstractmethod
import html
import flask

from .. import utils


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
    def get_rendition(self, output_scale=1, **kwargs):
        """ Get a rendition of the image with the specified output scale and specification.

        Returns: a tuple of (url, size) for the image. """

    @abstractmethod
    def _get_img_attrs(self, style=None, **kwargs):
        pass

    def get_img_attrs(self, style=None, **kwargs):
        """ Get an attribute list (src, srcset, style, et al) for the image.

        style -- an optional list of CSS style fragments

        Returns: a dict of attributes e.g. {'src':'foo.jpg','srcset':'foo.jpg 1x, bar.jpg 2x']
        """

        if 'prefix' in kwargs:
            attr_prefixes = kwargs.get('prefix')
            if isinstance(kwargs['prefix'], str):
                attr_prefixes = [attr_prefixes]

            for prefix in attr_prefixes:
                for k, val in kwargs.items():
                    if k.startswith(prefix):
                        kwargs[k[len(prefix):]] = val

        return self._get_img_attrs(style, **kwargs)

    def get_img_tag(self, title='', alt_text='', **kwargs):
        """ Build a <img> tag for the image with the specified options.

        Returns: an HTML fragment. """

        kwargs = {**kwargs}

        try:
            style = []

            for key in ('img_style', 'style'):
                if key in kwargs:
                    if isinstance(kwargs[key], (list, tuple)):
                        style += kwargs[key]
                    else:
                        style.append(kwargs[key])

                    del kwargs[key]

            if 'shape' in kwargs:
                shape = self._get_shape_style(**kwargs)
                if shape:
                    style.append("shape-outside: url('{}')".format(shape))

            attrs = {
                'alt': alt_text,
                'title': title,
                **self.get_img_attrs(style, **kwargs)
            }

            return flask.Markup(
                self._wrap_link_target(
                    kwargs,
                    utils.make_tag(
                        'img', attrs, start_end=kwargs.get('xhtml')),
                    title))
        except FileNotFoundError as error:
            text = '<span class="error">Image not found: <code>{}</code>'.format(
                html.escape(error.filename))
            if ' ' in error.filename:
                text += ' (Did you forget a <code>|</code>?)'
            text += '</span>'
            return flask.Markup(text)

    def _get_shape_style(self, **kwargs):
        shape = kwargs['shape']

        # Only pull in size-related attributes (e.g. no format, background,
        # etc.)
        size_args = {k: v for k, v in kwargs.items() if k in (
            'width', 'height', 'max_width', 'max_height', 'absolute'
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

    def get_css_background(self, uncomment=False, **kwargs):
        """ Get the CSS background attributes for an element.

        Additional arguments:

        uncomment -- surround the attributes with `*/` and `/*` so that the
            template tag can be kept inside a comment block, to keep syntax
            highlighters happy
        """

        text = self._css_background(**kwargs)
        if uncomment:
            text = ' */ {} /* '.format(text)

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

    def _wrap_link_target(self, kwargs, text, title):
        if 'link' in kwargs and kwargs['link'] is not None:
            return '{}{}</a>'.format(
                utils.make_tag(
                    'a', {'href': utils.remap_link_target(
                        kwargs['link'], kwargs.get('absolute')
                    )}),
                text)

        if 'gallery_id' in kwargs and kwargs['gallery_id'] is not None:
            return '{}{}</a>'.format(
                self._fullsize_link_tag(kwargs, title), text)

        return text

    def get_fullsize(self, kwargs):
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

    def _fullsize_link_tag(self, kwargs, title):
        """ Render a <a href> that points to the fullsize rendition specified """

        return utils.make_tag('a', {
            'href': self.get_fullsize(kwargs),
            'data-lightbox': kwargs['gallery_id'],
            'title': title
        })