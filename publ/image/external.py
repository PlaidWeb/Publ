""" Functionality for images external to the content directory """

import html
import os.path
import urllib.parse
from abc import abstractmethod

import flask

from .image import Image


class ExternalImage(Image):
    """ Base class for images which are rendered by external means """

    @abstractmethod
    def _get_url(self, absolute):
        """ Implemented by subclasses to actually map the URL """

    CSS_SIZE_MODE = {
        'fit': 'contain',
        'fill': 'cover'
    }

    def get_rendition(self, output_scale=1, **kwargs):
        # pylint: disable=unused-argument
        return self._get_url(kwargs.get('absolute')), None

    def _get_img_attrs(self, spec, style_parts):
        url = self._get_url(spec.get('absolute'))

        attrs = {}
        if 'class' in spec or 'img_class' in spec:
            attrs['class'] = spec.get('class', spec.get('img_class'))
        if 'id' in spec:
            attrs['id'] = spec['id']

        # try to fudge the sizing
        max_width = spec.get('max_width')
        width = spec.get('width') or max_width
        max_height = spec.get('max_height')
        height = spec.get('height') or max_height
        size_mode = spec.get('resize', 'fit')

        if width and max_width and max_width < width:
            if height:
                height = height * max_width / width
            width = max_width
        if height and max_height and max_height < height:
            if width:
                width = width * max_height / height
            height = max_height

        if width and height and size_mode != 'stretch':
            style_parts += [
                'background-image:url(\'{}\')'.format(html.escape(url)),
                'background-size:{}'.format(self.CSS_SIZE_MODE[size_mode]),
                'background-position:{:.1f}% {:.1f}%'.format(
                    spec.get('fill_crop_x', 0.5) * 100,
                    spec.get('fill_crop_y', 0.5) * 100),
                'background-repeat:no-repeat'
            ]
            attrs['src'] = flask.url_for(
                'chit', _external=spec.get('absolute'))
        else:
            attrs['src'] = url

        if width:
            attrs['width'] = width
        if height:
            attrs['height'] = height

        return attrs

    def _css_background(self, **kwargs) -> str:
        """ Get the CSS background-image for the remote image """
        return 'background-image: url("{}");'.format(self._get_url(kwargs.get('absolute')))

    @property
    def _filename(self) -> str:
        return os.path.basename(urllib.parse.urlparse(self._get_url(True)).path)
