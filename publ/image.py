# image.py
''' Managing image renditions '''

from __future__ import absolute_import, with_statement

import os
import hashlib
import logging
import html
import re
import ast
import concurrent.futures
import threading
import tempfile
import shutil

import PIL.Image
from werkzeug.utils import cached_property
import flask

from . import config
from . import model, utils

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


class Image:
    """ Base class for image handlers """

    def get_rendition(self, output_scale=1, **kwargs):
        """ Get a rendition of the image with the specified output scale and specification.

        Returns: a tuple of (url, size) for the image. """
        pass

    def get_img_tag(self, title='', alt_text='', **kwargs):
        """ Build a <img> tag for the image with the specified options.

        Returns: an HTML fragment. """
        pass

    def get_css_background(self, **kwargs):
        """ Build CSS background-image properties that apply this image.

        Returns: a CSS fragment. """
        pass

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

    def _fullsize_link_tag(self, kwargs, title):
        """ Render a <a href> that points to the fullsize rendition specified """
        fullsize_args = {}

        if 'absolute' in kwargs:
            fullsize_args = kwargs['absolute']

        for key in ['width', 'height', 'quality', 'format', 'background']:
            fsk = 'fullsize_' + key
            if fsk in kwargs:
                fullsize_args[key] = kwargs[fsk]

        img_fullsize, _ = self.get_rendition(1, **fullsize_args)

        return utils.make_tag('a', {
            'href': img_fullsize,
            'data-lightbox': kwargs['gallery_id'],
            'title': title
        })


class _NullLock():
    """ A fake "lock" that lets us not actually lock anymore """
    # pylint: disable=too-few-public-methods

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def __enter__(self):
        pass


class LocalImage(Image):
    """ The basic Image class, which knows about the base version and how to
    generate renditions from it """

    _thread_pool = None
    _null_lock = _NullLock()

    def __init__(self, record):
        """ Get the base image from an index record """
        super().__init__()
        self._record = record
        self._lock = threading.Lock()

    def get_rendition(self, output_scale=1, **kwargs):
        """
        Get the rendition for this image, generating it if necessary.
        Returns a tuple of `(relative_path, width, height)`, where relative_path
        is relative to the static file directory (i.e. what one would pass into
        `get_static()`)

        output_scale -- the upsample factor for the requested rendition

        Keyword arguments:

        scale -- the downsample factor for the base rendition
        scale_min_width -- the minimum width after downsampling
        scale_min_height -- the minimum height after downsampling
        width -- the width to target
        height -- the height to target
        max_width -- the maximum width
        max_height -- the maximum height
        resize -- how to fit the width and height; "fit", "fill", or "stretch"
        fill_crop_x -- horizontal offset fraction for resize="fill"
        fill_crop_y -- vertical offset fraction for resize="fill"
        format -- output format
        background -- background color when converting transparent to opaque
        quality -- the JPEG quality to save the image as
        quantize -- how large a palette to use for GIF or PNG images
        """

        basename, ext = os.path.splitext(
            os.path.basename(self._record.file_path))
        basename = utils.make_slug(basename)

        if kwargs.get('format'):
            ext = '.' + kwargs['format']

        # The spec for building the output filename
        out_spec = [basename, self._record.checksum[-10:]]

        out_args = {}
        if ext in ['.png', '.jpg', '.jpeg']:
            out_args['optimize'] = True

        size, box = self.get_rendition_size(kwargs, output_scale)
        if size and (size[0] < self._record.width or size[1] < self._record.height):
            out_spec.append('x'.join([str(v) for v in size]))
        if box:
            out_spec.append('-'.join([str(v) for v in box]))

        # Set RGBA flattening options
        flatten = self._record.transparent and ext not in ['.png', '.gif']
        if flatten and 'background' in kwargs:
            bg_color = kwargs['background']
            if isinstance(bg_color, (tuple, list)):
                out_spec.append('b' + '-'.join([str(a) for a in bg_color]))
            else:
                out_spec.append('b' + str(bg_color))

        # Set JPEG quality
        if (ext == '.jpg' or ext == '.jpeg') and kwargs.get('quality'):
            out_spec.append('q' + str(kwargs['quality']))
            out_args['quality'] = kwargs['quality']

        # Build the output filename
        out_basename = '_'.join([str(s) for s in out_spec]) + ext
        out_rel_path = os.path.join(
            config.image_output_subdir,
            self._record.checksum[0:2],
            self._record.checksum[2:6],
            out_basename)
        out_fullpath = os.path.join(config.static_folder, out_rel_path)

        if os.path.isfile(out_fullpath):
            return utils.static_url(out_rel_path, kwargs.get('absolute')), size

        if not LocalImage._thread_pool:
            logger.info("Starting LocalImage threadpool")
            LocalImage._thread_pool = concurrent.futures.ThreadPoolExecutor(
                thread_name_prefix="Renderer")

        LocalImage._thread_pool.submit(
            self._render, out_fullpath, size, box, flatten, kwargs, out_args)

        return flask.url_for('async', filename=out_rel_path), size

    @cached_property
    def _image(self):
        with self._lock:
            image = PIL.Image.open(self._record.file_path)

        return image

    def _render(self, path, size, box, flatten, kwargs, out_args):  # pylint:disable=too-many-arguments
        if not os.path.isfile(path):
            logger.info("Rendering file %s", path)
            try:
                if not os.path.isdir(os.path.dirname(path)):
                    os.makedirs(os.path.dirname(path))

                _, ext = os.path.splitext(path)

                image = self._image
                lock = self._lock

                paletted = image.mode == 'P'
                if paletted:
                    image = image.convert('RGB')

                if size:
                    with lock:
                        image = image.resize(size=size, box=box,
                                             resample=PIL.Image.LANCZOS)
                    lock = LocalImage._null_lock

                if flatten:
                    with lock:
                        image = self.flatten(image, kwargs.get('background'))
                    lock = LocalImage._null_lock

                if ext == '.gif' or (ext == '.png' and (paletted or kwargs.get('quantize'))):
                    with lock:
                        image = image.quantize(kwargs.get('quantize', 256))
                    lock = LocalImage._null_lock

                with self._lock, tempfile.NamedTemporaryFile(suffix=ext, delete=False) as file:
                    temp_path = file.name
                    image.save(file, **out_args)
                shutil.move(temp_path, path)

                logger.info("%s: complete", path)
            except Exception:  # pylint: disable=broad-except
                logger.exception("Failed to render %s -> %s",
                                 self._record.file_path, path)

    def get_rendition_size(self, spec, output_scale):
        """
        Wrapper to determine the overall rendition size and cropping box

        Returns tuple of (size,box)
        """

        mode = spec.get('resize', 'fit')

        if mode == 'fit':
            return self.get_rendition_fit_size(spec, output_scale)

        if mode == 'fill':
            return self.get_rendition_fill_size(spec, output_scale)

        if mode == 'stretch':
            return self.get_rendition_stretch_size(spec, output_scale)

        raise ValueError("Unknown resize mode {}".format(mode))

    def get_rendition_fit_size(self, spec, output_scale):
        """ Determine the scaled size based on the provided spec """

        input_w = self._record.width  # input width
        input_h = self._record.height  # input height

        width = input_w
        height = input_h

        scale = spec.get('scale')
        if scale:
            width = width / scale
            height = height / scale

        min_width = spec.get('scale_min_width')
        if min_width and width < min_width:
            height = height * min_width / width
            width = min_width

        min_height = spec.get('scale_min_height')
        if min_height and height < min_height:
            width = width * min_height / height
            height = min_height

        tgt_width, tgt_height = spec.get('width'), spec.get('height')

        if tgt_width and width > tgt_width:
            height = height * tgt_width / width
            width = tgt_width

        if tgt_height and height > tgt_height:
            width = width * tgt_height / height
            height = tgt_height

        tgt_width, tgt_height = spec.get('max_width'), spec.get('max_height')

        if tgt_width and width > tgt_width:
            height = height * tgt_width / width
            width = tgt_width

        if tgt_height and height > tgt_height:
            width = width * tgt_height / height
            height = tgt_height

        width = width * output_scale
        height = height * output_scale

        # Never scale to larger than the base rendition
        width = min(round(width), input_w)
        height = min(round(height), input_h)

        return (width, height), None

    def get_rendition_fill_size(self, spec, output_scale):
        """ Determine the scale-crop size given the provided spec """

        input_w = self._record.width
        input_h = self._record.height

        width = input_w
        height = input_h

        scale = spec.get('scale')
        if scale:
            width = width / scale
            height = height / scale

        if spec.get('scale_min_width'):
            width = max(width, spec['spec_min_width'])

        if spec.get('scale_min_height'):
            height = max(height, spec['scale_min_height'])

        if spec.get('width'):
            width = min(width, spec['width'])
        if spec.get('max_width'):
            width = min(width, spec['max_width'])

        if spec.get('height'):
            height = min(height, spec['height'])
        if spec.get('max_height'):
            height = min(height, spec['max_height'])

        width = width * output_scale
        height = height * output_scale

        # Never scale to larger than the base rendition (but keep the output
        # aspect)
        if width > input_w:
            height = height * input_w / width
            width = input_w

        if height > input_h:
            width = width * input_h / height
            height = input_h

        # Determine the box size
        box_w = min(input_w, round(width * input_h / height))
        box_h = min(input_h, round(height * input_w / width))

        # Box offset
        box_x = round((input_w - box_w) * spec.get('fill_crop_x', 0.5))
        box_y = round((input_h - box_h) * spec.get('fill_crop_y', 0.5))

        return (round(width), round(height)), (box_x, box_y, box_x + box_w, box_y + box_h)

    def get_rendition_stretch_size(self, spec, output_scale):
        """ Determine the scale-crop size given the provided spec """

        width = self._record.width
        height = self._record.height

        scale = spec.get('scale')
        if scale:
            width = width / scale
            height = height / scale

        min_width = spec.get('scale_min_width')
        if min_width and width < min_width:
            width = min_width

        min_height = spec.get('scale_min_height')
        if min_height and height < min_height:
            height = min_height

        tgt_width, tgt_height = spec.get('width'), spec.get('height')

        if tgt_width and width > tgt_width:
            width = tgt_width

        tgt_height = spec.get('height')
        if tgt_height and height > tgt_height:
            height = tgt_height

        tgt_width, tgt_height = spec.get('max_width'), spec.get('max_height')

        if tgt_width and width > tgt_width:
            width = tgt_width

        tgt_height = spec.get('height')
        if tgt_height and height > tgt_height:
            height = tgt_height

        width = width * output_scale
        height = height * output_scale

        return (round(width), round(height)), None

    @staticmethod
    def flatten(image, bgcolor=None):
        """ Flatten an image, with an optional background color """
        if bgcolor:
            background = PIL.Image.new('RGB', image.size, bgcolor)
            background.paste(image, mask=image.split()[3])
            return background

        return image.convert('RGB')

    def get_img_tag(self, title='', alt_text='', **kwargs):
        """ Get an <img> tag for this image, hidpi-aware """

        # Get the 1x and 2x renditions
        img_1x, size = self.get_rendition(
            1, **utils.remap_args(kwargs, {"quality": "quality_ldpi"}))
        img_2x, _ = self.get_rendition(
            2, **utils.remap_args(kwargs, {"quality": "quality_hdpi"}))

        text = utils.make_tag('img', {
            'src': img_1x,
            'width': size[0],
            'height': size[1],
            'srcset': "{} 1x, {} 2x".format(img_1x, img_2x) if img_1x != img_2x else None,
            'title': title,
            'alt': alt_text
        })

        # Wrap it in a link as appropriate
        return flask.Markup(self._wrap_link_target(kwargs, text, title))

    def get_css_background(self, **kwargs):
        """ Get the CSS specifiers for this as a hidpi-capable background image """

        # Get the 1x and 2x renditions
        img_1x, _ = self.get_rendition(
            1, **utils.remap_args(kwargs, {"quality": "quality_ldpi"}))
        img_2x, _ = self.get_rendition(
            2, **utils.remap_args(kwargs, {"quality": "quality_hdpi"}))

        tmpl = 'background-image: url("{s1x}");'
        if img_1x != img_2x:
            image_set = 'image-set(url("{s1x}") 1x, url("{s2x}") 2x)'
            tmpl += 'background-image: {ss};background-image: -webkit-{ss};'.format(
                ss=image_set)
        return tmpl.format(s1x=img_1x, s2x=img_2x)


class RemoteImage(Image):
    """ An image that points to a remote URL """

    CSS_SIZE_MODE = {
        'fit': 'contain',
        'fill': 'cover'
    }

    def __init__(self, url):
        super().__init__()
        self.url = url

    def get_rendition(self, output_scale=1, **kwargs):
        # pylint: disable=unused-argument
        return self.url, None

    def get_img_tag(self, title='', alt_text='', **kwargs):
        attrs = {
            'title': title,
            'alt': alt_text
        }

        # try to fudge the sizing
        width = kwargs.get('width')
        height = kwargs.get('height')
        size_mode = kwargs.get('resize', 'fit')

        if width and height and size_mode != 'stretch':
            attrs['style'] = ';'.join([
                'background-image:url(\'{}\')'.format(html.escape(self.url)),
                'background-size:{}'.format(self.CSS_SIZE_MODE[size_mode]),
                'background-position:{:.1f}% {:.1f}%'.format(
                    kwargs.get('fill_crop_x', 0.5) * 100,
                    kwargs.get('fill_crop_y', 0.5) * 100),
                'background-repeat:no-repeat'
            ])
            attrs['src'] = flask.url_for(
                'chit', _external=kwargs.get('absolute'))
        else:
            attrs['src'] = self.url

        attrs['width'] = width
        attrs['height'] = height

        return self._wrap_link_target(kwargs, utils.make_tag('img', attrs), title)

    def get_css_background(self, **kwargs):
        """ Get the CSS background-image for the remote image """
        return 'background-image: url("{}");'.format(self.url)


class StaticImage(Image):
    """ An image that points to a static resource """

    def __init__(self, path):
        super().__init__()
        self.path = path

    def get_rendition(self, output_scale=1, **kwargs):
        url = utils.static_url(self.path, absolute=kwargs.get('absolute'))
        return RemoteImage(url).get_rendition(output_scale, **kwargs)

    def get_img_tag(self, title='', alt_text='', **kwargs):
        url = utils.static_url(self.path, absolute=kwargs.get('absolute'))
        return RemoteImage(url).get_img_tag(title, alt_text, **kwargs)

    def get_css_background(self, **kwargs):
        url = utils.static_url(self.path, absolute=kwargs.get('absolute'))
        return RemoteImage(url).get_css_background(**kwargs)


class ImageNotFound(Image):
    """ A fake image that prints out appropriate error messages for missing images """

    def __init__(self, path):
        super().__init__()
        self.path = path

    def get_rendition(self, output_scale=1, **kwargs):
        # pylint:disable=unused-argument
        return 'missing file ' + self.path

    def get_img_tag(self, title='', alt_text='', **kwargs):
        # pylint:disable=unused-argument
        text = '<span class="error">Image not found: <code>{}</code>'.format(
            html.escape(self.path))
        if ' ' in self.path:
            text += ' (Did you forget a <code>|</code>?)'
        text += '</span>'
        return text

    def get_css_background(self, **kwargs):
        return '/* not found: {} */'.format(self.path)


def get_image(path, search_path):
    """ Get an Image object. If the path is given as absolute, it will be
    relative to the content directory; otherwise it will be relative to the
    search path.

    path -- the image's filename
    search_path -- a search path for the image (string or list of strings)
    """

    if path.startswith('@'):
        return StaticImage(path[1:])

    if path.startswith('//') or '://' in path:
        return RemoteImage(path)

    if os.path.isabs(path):
        file_path = utils.find_file(os.path.relpath(
            path, '/'), config.content_folder)
    else:
        file_path = utils.find_file(path, search_path)
    if not file_path:
        return ImageNotFound(path)

    record = model.Image.get_or_none(file_path=file_path)
    fingerprint = utils.file_fingerprint(file_path)
    if not record or record.fingerprint != fingerprint:
        # Reindex the file
        logger.info("Updating image %s -> %s", file_path, fingerprint)

        # compute the md5sum; from https://stackoverflow.com/a/3431838/318857
        md5 = hashlib.md5()
        with open(file_path, 'rb') as file:
            for chunk in iter(lambda: file.read(16384), b""):
                md5.update(chunk)

        image = PIL.Image.open(file_path)
        values = {
            'checksum': md5.hexdigest(),
            'width': image.width,
            'height': image.height,
            'fingerprint': fingerprint,
            'transparent': image.mode == 'RGBA'
        }
        record, created = model.Image.get_or_create(
            file_path=file_path, defaults=values)
        if not created:
            record.update(**values).where(model.Image.id ==
                                          record.id).execute()

    return LocalImage(record)


def parse_arglist(args):
    """ Parses an arglist into arguments for Image, as a kwargs dict """
    # per https://stackoverflow.com/a/49723227/318857

    args = 'f({})'.format(args)
    tree = ast.parse(args)
    funccall = tree.body[0].value

    args = [ast.literal_eval(arg) for arg in funccall.args]
    kwargs = {arg.arg: ast.literal_eval(arg.value)
              for arg in funccall.keywords}

    if len(args) > 2:
        raise TypeError(
            "Expected at most 2 positional args but {} were given".format(len(args)))

    if len(args) >= 1:
        kwargs['width'] = int(args[0])
    if len(args) >= 2:
        kwargs['height'] = int(args[1])

    return kwargs


def parse_alt_text(alt):
    """ Parses the arguments out from a Publ-Markdown alt text into a tuple of text, args """
    match = re.match(r'([^\{]*)(\{(.*)\})$', alt)
    if match:
        alt = match.group(1)
        args = parse_arglist(match.group(3))
    else:
        args = {}

    return alt, args


def parse_image_spec(spec):
    """ Parses out a Publ-Markdown image spec into a tuple of path, args, title """

    # I was having trouble coming up with a single RE that did it right,
    # so let's just break it down into sub-problems. First, parse out the
    # alt text...
    match = re.match(r'(.+)\s+\"(.*)\"\s*$', spec)
    if match:
        spec, title = match.group(1, 2)
    else:
        title = None

    # and now parse out the arglist
    match = re.match(r'([^\{]*)(\{(.*)\})\s*$', spec)
    if match:
        spec = match.group(1)
        args = parse_arglist(match.group(3))
    else:
        args = {}

    return spec, args, (title and html.unescape(title))


def get_spec_list(image_specs, container_args):
    """ Given a list of specs and a set of container args, return the final
    container argument list """

    spec_list = [spec.strip() for spec in image_specs.split('|')]

    if 'count' in container_args:
        if 'count_offset' in container_args:
            spec_list = spec_list[container_args['count_offset']:]
        spec_list = spec_list[:container_args['count']]

    return spec_list
