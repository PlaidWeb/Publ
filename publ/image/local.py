""" Functions for manipulating images stored within local content """

import concurrent.futures
import functools
import logging
import os
import shutil
import tempfile
import threading
import time

from werkzeug.utils import cached_property
import flask
import PIL.Image

from .. import config
from .. import utils
from .image import Image

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


def fix_orientation(image):
    """ adapted from https://stackoverflow.com/a/30462851/318857

        Apply Image.transpose to ensure 0th row of pixels is at the visual
        top of the image, and 0th column is the visual left-hand side.
        Return the original image if unable to determine the orientation.

        As per CIPA DC-008-2012, the orientation field contains an integer,
        1 through 8. Other values are reserved.
    """

    exif_orientation_tag = 0x0112
    exif_transpose_sequences = [
        [],
        [],
        [PIL.Image.FLIP_LEFT_RIGHT],
        [PIL.Image.ROTATE_180],
        [PIL.Image.FLIP_TOP_BOTTOM],
        [PIL.Image.FLIP_LEFT_RIGHT, PIL.Image.ROTATE_90],
        [PIL.Image.ROTATE_270],
        [PIL.Image.FLIP_TOP_BOTTOM, PIL.Image.ROTATE_90],
        [PIL.Image.ROTATE_90],
    ]

    try:
        # pylint:disable=protected-access
        orientation = image._getexif()[exif_orientation_tag]
        sequence = exif_transpose_sequences[orientation]
        return functools.reduce(type(image).transpose, sequence, image)
    except (TypeError, AttributeError, KeyError):
        # either no EXIF tags or no orientation tag
        pass
    return image


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

            image = fix_orientation(image)

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

    def _get_img_attrs(self, kwargs, style_parts):
        """ Get the attributes of an an <img> tag for this image, hidpi-aware """
        # pylint:disable=unused-argument

        # Get the 1x and 2x renditions
        img_1x, img_2x, size = self._get_renditions(kwargs)

        attrs = {
            'src': img_1x,
            'width': size[0],
            'height': size[1]
        }

        if img_1x != img_2x:
            attrs['srcset'] = "{} 1x, {} 2x".format(img_1x, img_2x)

        return attrs

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
