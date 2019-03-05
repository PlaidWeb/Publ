# image.py
''' Managing image renditions '''

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
import time
import random
import io
import errno
from abc import ABC, abstractmethod

import PIL.Image
from werkzeug.utils import cached_property
import flask
from pony import orm

from . import config
from . import model, utils

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


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
    def get_img_attrs(self, style=None, **kwargs):
        """ Get an attribute list (src, srcset, style, et al) for the image.

        style -- an optional list of CSS style fragments

        Returns: a dict of attributes e.g. {'src':'foo.jpg','srcset':'foo.jpg 1x, bar.jpg 2x']
        """

    def get_img_tag(self, title='', alt_text='', **kwargs):
        """ Build a <img> tag for the image with the specified options.

        Returns: an HTML fragment. """

        try:
            style = []

            for key in ('img_style', 'style'):
                if key in kwargs:
                    if isinstance(kwargs[key], (list, tuple)):
                        style += kwargs[key]
                    else:
                        style.append(kwargs[key])

                    kwargs = {**kwargs}
                    del kwargs[key]

            if 'shape' in kwargs:
                shape = self._get_shape_style(**kwargs)
                if shape:
                    style.append("shape-outside: url('{}')".format(shape))

            attrs = {
                'alt_text': alt_text,
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


class LocalImage(Image):
    """ The basic Image class, which knows about the base version and how to
    generate renditions from it """

    _thread_pool = None

    @staticmethod
    def thread_pool():
        """ Get the rendition threadpool """
        if not LocalImage._thread_pool:
            logger.info("Starting LocalImage threadpool")
            LocalImage._thread_pool = concurrent.futures.ThreadPoolExecutor(
                thread_name_prefix="Renderer")
        return LocalImage._thread_pool

    def __init__(self, record, search_path):
        """ Get the base image from an index record """
        super().__init__(search_path)

        self._record = record
        self._lock = threading.Lock()

    def _key(self):
        return LocalImage, self._record

    def get_rendition(self, output_scale=1, **kwargs):
        # pylint:disable=too-many-locals
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
        crop -- box to crop the original image into (left, top, right, bottom)
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

        crop = self._parse_tuple_string(kwargs.get('crop'))

        size, box = self.get_rendition_size(kwargs, output_scale, crop)
        box = self._adjust_crop_box(box, crop)

        if size and (size[0] < self._record.width or size[1] < self._record.height):
            out_spec.append('x'.join([str(v) for v in size]))

        if box:
            # pylint:disable=not-an-iterable
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
        if ext in ('.jpg', '.jpeg') and kwargs.get('quality'):
            out_spec.append('q' + str(kwargs['quality']))
            out_args['quality'] = kwargs['quality']
        if ext in ('.jpg', '.jpeg'):
            out_args['optimize'] = True

        # Build the output filename
        out_basename = '_'.join([str(s) for s in out_spec]) + ext
        out_rel_path = os.path.join(
            config.image_output_subdir,
            self._record.checksum[0:2],
            self._record.checksum[2:6],
            out_basename)
        out_fullpath = os.path.join(config.static_folder, out_rel_path)

        if os.path.isfile(out_fullpath):
            os.utime(out_fullpath)
            return utils.static_url(out_rel_path, kwargs.get('absolute')), size

        LocalImage.thread_pool().submit(
            self._render, out_fullpath, size, box, flatten, kwargs, out_args)

        return flask.url_for('async', filename=out_rel_path, _external=kwargs.get('absolute')), size

    @cached_property
    def _image(self):
        with self._lock:
            image = PIL.Image.open(self._record.file_path)

        return image

    @staticmethod
    def _adjust_crop_box(box, crop):
        """ Given a fit box and a crop box, adjust one to the other """

        if crop and box:
            # Both boxes are the same size; just line them up.
            return (box[0] + crop[0], box[1] + crop[1],
                    box[2] + crop[0], box[3] + crop[1])

        if crop:
            # We don't have a fit box, so just convert the crop box
            return (crop[0], crop[1], crop[0] + crop[2], crop[1] + crop[3])

        # We don't have a crop box, so return the fit box (even if it's None)
        return box

    @staticmethod
    def _parse_tuple_string(argument):
        """ Return a tuple from parsing 'a,b,c,d' -> (a,b,c,d) """
        if isinstance(argument, str):
            return tuple(int(p.strip()) for p in argument.split(','))
        return argument

    @staticmethod
    def _crop_to_box(crop):
        # pylint:disable=invalid-name
        x, y, w, h = crop
        return (x, y, x + w, y + h)

    def _render(self, path, size, box, flatten, kwargs, out_args):
        # pylint:disable=too-many-arguments
        image = self._image

        with self._lock:
            if os.path.isfile(path):
                # file already exists
                return

            logger.info("Rendering file %s", path)

            try:
                os.makedirs(os.path.dirname(path))
            except FileExistsError:
                pass

            _, ext = os.path.splitext(path)

            try:
                paletted = image.mode == 'P'
                if paletted:
                    image = image.convert('RGBA')

                if size:
                    image = image.resize(size=size, box=box,
                                         resample=PIL.Image.LANCZOS)

                if flatten:
                    image = self.flatten(image, kwargs.get('background'))
                    image = image.convert('RGB')

                if ext == '.gif' or (ext == '.png' and (paletted or kwargs.get('quantize'))):
                    image = image.quantize(kwargs.get('quantize', 256))

                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as file:
                    temp_path = file.name
                    image.save(file, **out_args)
                shutil.move(temp_path, path)

                logger.info("%s: complete", path)
            except Exception:  # pylint: disable=broad-except
                logger.exception("Failed to render %s -> %s",
                                 self._record.file_path, path)

    def get_rendition_size(self, spec, output_scale, crop):
        """
        Wrapper to determine the overall rendition size and cropping box

        Returns tuple of (size,box)
        """

        if crop:
            # Use the cropping rectangle size
            _, _, width, height = crop
        else:
            # Use the original image size
            width = self._record.width
            height = self._record.height

        mode = spec.get('resize', 'fit')
        if mode == 'fit':
            return self.get_rendition_fit_size(spec, width, height, output_scale)

        if mode == 'fill':
            return self.get_rendition_fill_size(spec, width, height, output_scale)

        if mode == 'stretch':
            return self.get_rendition_stretch_size(spec, width, height, output_scale)

        raise ValueError("Unknown resize mode {}".format(mode))

    @staticmethod
    def get_rendition_fit_size(spec, input_w, input_h, output_scale):
        """ Determine the scaled size based on the provided spec """

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

    @staticmethod
    def get_rendition_fill_size(spec, input_w, input_h, output_scale):
        """ Determine the scale-crop size given the provided spec """

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

    @staticmethod
    def get_rendition_stretch_size(spec, input_w, input_h, output_scale):
        """ Determine the scale-crop size given the provided spec """

        width = input_w
        height = input_h

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

    def _get_renditions(self, kwargs):
        """ Get a bunch of renditions; returns a tuple of 1x, 2x, size """
        img_1x, size = self.get_rendition(
            1, **utils.remap_args(kwargs, {"quality": "quality_ldpi"}))
        img_2x, _ = self.get_rendition(
            2, **utils.remap_args(kwargs, {"quality": "quality_hdpi"}))

        return (img_1x, img_2x, size)

    def get_img_attrs(self, style=None, **kwargs):
        """ Get an <img> tag for this image, hidpi-aware """

        # Get the 1x and 2x renditions
        img_1x, img_2x, size = self._get_renditions(kwargs)

        return {
            'src': img_1x,
            'width': size[0],
            'height': size[1],
            'srcset': "{} 1x, {} 2x".format(img_1x, img_2x) if img_1x != img_2x else None,
            'style': ';'.join(style) if style else None,
            'class': kwargs.get('class', kwargs.get('img_class')),
            'id': kwargs.get('img_id')
        }

    def _css_background(self, **kwargs):
        """ Get the CSS specifiers for this as a hidpi-capable background image """

        # Get the 1x and 2x renditions
        img_1x, img_2x, _ = self._get_renditions(kwargs)

        tmpl = 'background-image: url("{s1x}");'
        if img_1x != img_2x:
            image_set = 'image-set(url("{s1x}") 1x, url("{s2x}") 2x)'
            tmpl += 'background-image: {ss};background-image: -webkit-{ss};'.format(
                ss=image_set)
        return tmpl.format(s1x=img_1x, s2x=img_2x)

    @staticmethod
    def clean_cache(max_age):
        """ Clean the rendition cache of files older than max_age seconds """
        LocalImage.thread_pool().submit(LocalImage._clean_cache, max_age)

    @staticmethod
    def _clean_cache(max_age):
        threshold = time.time() - max_age

        # delete expired files
        for root, _, files in os.walk(os.path.join(config.static_folder,
                                                   config.image_output_subdir)):
            for file in files:
                path = os.path.join(root, file)
                if os.path.isfile(path) and os.stat(path).st_mtime < threshold:
                    try:
                        os.unlink(path)
                        logger.info("Expired stale rendition %s (mtime=%d threshold=%d)",
                                    path, os.stat(path).st_mtime, threshold)
                    except FileNotFoundError:
                        pass
                if os.path.isdir(path) and next(os.scandir(path), None) is None:
                    try:
                        os.removedirs(path)
                        logger.info("Removed empty cache directory %s", path)
                    except OSError:
                        logger.exception("Couldn't remove %s", path)


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

    def get_img_attrs(self, style=None, **kwargs):
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

        style_parts = [*style] if style else []

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

        attrs['width'] = width
        attrs['height'] = height

        if style_parts:
            attrs['style'] = ';'.join(style_parts)

        return attrs

    def _css_background(self, **kwargs):
        """ Get the CSS background-image for the remote image """
        return 'background-image: url("{}");'.format(self._get_url(kwargs.get('absolute')))


class FileAsset(ExternalImage):
    """ An 'image' which is actually a static file asset """

    def __init__(self, record, search_path):
        super().__init__(search_path)
        self.filename = record.asset_name

    def _key(self):
        return FileAsset, self.filename

    def _get_url(self, absolute):
        return flask.url_for('asset', filename=self.filename, _external=absolute)


class RemoteImage(ExternalImage):
    """ An image that points to a remote URL """

    def __init__(self, url, search_path):
        super().__init__(search_path)
        self.url = url

    def _key(self):
        return RemoteImage, self.url

    def _get_url(self, absolute):
        # pylint: disable=unused-argument
        return self.url


class StaticImage(ExternalImage):
    """ An image that points to a static resource """

    def __init__(self, path, search_path):
        super().__init__(search_path)
        self.path = path

    def _key(self):
        return StaticImage, self.path

    def _get_url(self, absolute):
        return utils.static_url(self.path, absolute)


class ImageNotFound(Image):
    """ A fake image that prints out appropriate error messages for missing images """

    def __init__(self, path, search_path):
        super().__init__(search_path)
        self.path = path

    def _key(self):
        return ImageNotFound, self.path

    def get_rendition(self, output_scale=1, **kwargs):
        # pylint:disable=unused-argument
        raise FileNotFoundError(
            errno.ENOENT, os.strerror(errno.ENOENT), self.path)

    def get_img_attrs(self, style=None, **kwargs):
        # pylint:disable=unused-argument
        raise FileNotFoundError(
            errno.ENOENT, os.strerror(errno.ENOENT), self.path)

    def _css_background(self, **kwargs):
        return '/* not found: {} */'.format(self.path)


@orm.db_session(immediate=True)
def _get_asset(file_path):
    """ Get the database record for an asset file """
    record = model.Image.get(file_path=file_path)
    fingerprint = utils.file_fingerprint(file_path)
    if not record or record.fingerprint != fingerprint:
        # Reindex the file
        logger.info("Updating image %s -> %s", file_path, fingerprint)

        # compute the md5sum; from https://stackoverflow.com/a/3431838/318857
        md5 = hashlib.md5()
        with open(file_path, 'rb') as file:
            for chunk in iter(lambda: file.read(16384), b""):
                md5.update(chunk)

        values = {
            'file_path': file_path,
            'checksum': md5.hexdigest(),
            'fingerprint': fingerprint,
        }

        try:
            image = PIL.Image.open(file_path)
        except IOError:
            image = None

        if image:
            values['width'] = image.width
            values['height'] = image.height
            values['transparent'] = image.mode in ('RGBA', 'P')
            values['is_asset'] = False
        else:
            # PIL could not figure out what file type this is, so treat it as
            # an asset
            values['is_asset'] = True
            values['asset_name'] = os.path.join(values['checksum'][:5],
                                                os.path.basename(file_path))
        record = model.Image.get(file_path=file_path)
        if record:
            record.set(**values)
        else:
            record = model.Image(**values)
        orm.commit()

    return record


def get_image(path, search_path):
    """ Get an Image object. If the path is given as absolute, it will be
    relative to the content directory; otherwise it will be relative to the
    search path.

    path -- the image's filename
    search_path -- a search path for the image (string or list of strings)
    """

    if path.startswith('@'):
        return StaticImage(path[1:], search_path)

    if path.startswith('//') or '://' in path:
        return RemoteImage(path, search_path)

    if os.path.isabs(path):
        file_path = utils.find_file(os.path.relpath(
            path, '/'), config.content_folder)
    else:
        file_path = utils.find_file(path, search_path)
    if not file_path:
        return ImageNotFound(path, search_path)

    record = _get_asset(file_path)
    if record.is_asset:
        return FileAsset(record, search_path)
    return LocalImage(record, search_path)


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
    """ Given a list of specs and a set of container args, return a tuple of
    the final container argument list and the original list size """

    spec_list = [spec.strip() for spec in image_specs.split('|')]
    original_count = len(spec_list)

    if 'count' in container_args:
        if 'count_offset' in container_args:
            spec_list = spec_list[container_args['count_offset']:]
        spec_list = spec_list[:container_args['count']]

    return spec_list, original_count


def clean_cache(max_age):
    """ Clean the rendition cache of renditions which haven't been accessed in a while

    Arguments:

    max_age -- the TTL on a rendition, in seconds
    """

    LocalImage.clean_cache(max_age)


def get_async(filename):
    """ Asynchronously fetch an image """

    if os.path.isfile(os.path.join(config.static_folder, filename)):
        return flask.redirect(flask.url_for('static', filename=filename))

    retry_count = int(flask.request.args.get('retry_count', 0))
    if retry_count < 10:
        time.sleep(0.25)  # ghastly hack to get the client to backoff a bit
        return flask.redirect(flask.url_for('async',
                                            filename=filename,
                                            cb=random.randint(0, 2**48),
                                            retry_count=retry_count + 1))

    # the image isn't available yet; generate a placeholder and let the
    # client attempt to re-fetch periodically, maybe
    vals = [int(b) for b in hashlib.md5(
        filename.encode('utf-8')).digest()[0:12]]
    placeholder = PIL.Image.new('RGB', (2, 2))
    placeholder.putdata(list(zip(vals[0::3], vals[1::3], vals[2::3])))
    outbytes = io.BytesIO()
    placeholder.save(outbytes, "PNG")
    outbytes.seek(0)

    response = flask.make_response(
        flask.send_file(outbytes, mimetype='image/png'))
    response.headers['Refresh'] = 5
    return response
