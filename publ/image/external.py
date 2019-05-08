""" Functionality for images external to the content directory """

from abc import abstractmethod
import html

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

    def _get_img_attrs(self, kwargs, style_parts):
        url = self._get_url(kwargs.get('absolute'))

        attrs = {
            'class': kwargs.get('class', kwargs.get('img_class')),
            'id': kwargs.get('img_id'),
        }

        # try to fudge the sizing
        max_width = kwargs.get('max_width')
        width = kwargs.get('width') or max_width
        max_height = kwargs.get('max_height')
        height = kwargs.get('height') or max_height
        size_mode = kwargs.get('resize', 'fit')

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
                    kwargs.get('fill_crop_x', 0.5) * 100,
                    kwargs.get('fill_crop_y', 0.5) * 100),
                'background-repeat:no-repeat'
            ]
            attrs['src'] = flask.url_for(
                'chit', _external=kwargs.get('absolute'))
        else:
            attrs['src'] = url

        if width:
            attrs['width'] = width
        if height:
            attrs['height'] = height

        return attrs

    def _css_background(self, **kwargs):
        """ Get the CSS background-image for the remote image """
        return 'background-image: url("{}");'.format(self._get_url(kwargs.get('absolute')))
