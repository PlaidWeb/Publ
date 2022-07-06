""" Functions for manipulating images stored within local content """

import concurrent.futures
import functools
import logging
import os
import threading
import time
import typing

import flask
import itsdangerous
import PIL.Image
import slugify
from atomicwrites import atomic_write
from werkzeug.utils import cached_property

from .. import utils
from ..config import config
from .image import Image

LOGGER = logging.getLogger(__name__)

SizeType = typing.Tuple[int, int]
BoxType = typing.Tuple[int, int, int, int]
SizeSpecType = typing.Tuple[SizeType, typing.Optional[BoxType]]
PipelineEntry = typing.Tuple[typing.Optional[str],
                             typing.Optional[typing.Callable]]
ProcessingPipeline = typing.List[PipelineEntry]

# formats which support transparency
TRANSPARENCY_FORMATS = {'.gif', '.png', '.webp'}

# formats which support image quality
QUALITY_FORMATS = {'.jpg', '.jpeg', '.webp'}

# formats which support palettes
PALETTE_FORMATS = {'.gif', '.png', '.webp'}

# formats which support lossless compression
LOSSLESS_FORMATS = {'.webp'}

# formats which support image optimization
OPTIMIZE_FORMATS = {'.jpg', '.jpeg', '.png'}

# arguments that affect the final rendition
RENDITION_ARG_FILTER = {
    'scale', 'scale_min_width', 'scale_min_height',
    'crop',
    'width', 'height',
    'max_width', 'max_height',
    'resize',
    'fill_crop_x', 'fill_crop_y',
    'format',
    'background',
    'quality',
    'quantize',
}


def fix_orientation(image: PIL.Image) -> PIL.Image:
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
        # pylint:disable=consider-using-with
        if not LocalImage._thread_pool:
            LOGGER.info("Starting LocalImage threadpool")
            LocalImage._thread_pool = concurrent.futures.ThreadPoolExecutor(
                thread_name_prefix="Renderer",
                max_workers=config.image_render_threads)
        return LocalImage._thread_pool

    def __init__(self, record, search_path):
        """ Get the base image from an index record """
        super().__init__(search_path)

        self._record = record
        self._lock = threading.Lock()

    def _key(self):
        return LocalImage, self._record

    @property
    def _filename(self):
        return os.path.basename(self._record.file_path)

    def _get_rendition(self, output_scale=1, render=False, **kwargs):
        """ implements get_rendition and returns tuple of out_rel_path,size,pending """
        basename, ext = os.path.splitext(
            os.path.basename(self._record.file_path))
        basename = slugify.slugify(basename)

        if kwargs.get('format'):
            ext = '.' + kwargs['format']

        pipeline, out_args, size = self._build_pipeline(basename, ext, output_scale, kwargs)

        # Build the output filename
        out_basename = '_'.join([str(name) for name, _ in pipeline if name]) + ext
        out_rel_path = os.path.join(
            config.image_output_subdir,
            self._record.checksum[0:2],
            self._record.checksum[2:6],
            out_basename)
        out_fullpath = os.path.join(config.static_folder, out_rel_path)

        if os.path.isfile(out_fullpath):
            LOGGER.debug("rendition %s already exists", out_fullpath)
            os.utime(out_fullpath)
            pending = False
        elif render:
            LOGGER.debug("scheduling %s for render", out_fullpath)
            LocalImage.thread_pool().submit(
                self._render, out_fullpath, [op for _, op in pipeline if op], out_args)
            pending = True
        else:
            LOGGER.debug("rendition %s does not exist, waiting for a real request", out_fullpath)
            pending = True

        return out_rel_path, size, pending

    def _build_pipeline(self, basename, ext, output_scale, kwargs) -> typing.Tuple[
            ProcessingPipeline, typing.Dict, SizeType]:
        """
        Build the image processing pipeline

        Returns a tuple of ProcessingPipeline, output_args, size
        """

        pipeline: ProcessingPipeline = []

        # set the image basename
        pipeline.append((basename, None))
        pipeline.append((self._record.checksum[-10:], None))

        # Fix the EXIF orientation
        pipeline.append((None, fix_orientation))

        stash = {}
        out_args: typing.Dict[str, typing.Any] = {}
        if ext in OPTIMIZE_FORMATS:
            out_args['optimize'] = True

        # convert to RGBA
        def to_rgba(image):
            if image.mode == 'P':
                stash['paletted'] = True
                return image.convert('RGBA')
            return image

        pipeline.append((None, to_rgba))

        label: typing.Optional[str]

        # Set RGBA flattening options
        if (self._record.transparent and ext not in TRANSPARENCY_FORMATS) or 'background' in kwargs:
            bg_color = kwargs.get('background')
            if isinstance(bg_color, (tuple, list)):
                label = 'b' + '-'.join([str(a) for a in bg_color])
            elif bg_color:
                label = f'b{bg_color}'
            else:
                label = None
            pipeline.append((label, lambda image: self.flatten(image, bg_color)))

        size, cropscale = self._build_pipeline_cropscale(output_scale, kwargs)
        if cropscale:
            pipeline.append(cropscale)

        # Set image quantization options
        if ext in PALETTE_FORMATS:
            quantize = kwargs.get('quantize')

            def to_paletted(image):
                if ext == '.gif' or stash.get('paletted') or quantize:
                    return image.quantize(colors=quantize or 256)
                return image
            pipeline.append((f'p{quantize}' if quantize else None, to_paletted))

        # Set compression quality
        if ext in LOSSLESS_FORMATS and kwargs.get('lossless'):
            pipeline.append(('l', None))
            out_args['lossless'] = True
            if ext in QUALITY_FORMATS:
                out_args['quality'] = 100
        elif ext in QUALITY_FORMATS and kwargs.get('quality'):
            pipeline.append((f'q{kwargs["quality"]}', None))
            out_args['quality'] = kwargs['quality']

        return pipeline, out_args, size

    def _build_pipeline_cropscale(self, output_scale, kwargs) -> typing.Tuple[
            SizeType,
            typing.Optional[PipelineEntry]]:
        crop = utils.parse_tuple_string(kwargs.get('crop'))
        size, box = self.get_rendition_size(kwargs, output_scale, crop)

        if crop and box:
            # Both boxes are the same size; just line them up.
            box = (box[0] + crop[0], box[1] + crop[1],
                   box[2] + crop[0], box[3] + crop[1])
        elif crop:
            # We don't have a fit box, so just convert the crop box
            box = (crop[0], crop[1], crop[0] + crop[2], crop[1] + crop[3])

        # Apply the image cropscale
        if box or size[0] < self._record.width or size[1] < self._record.height:
            label = 'x'.join([str(v) for v in size])
            if box:
                label += '_' + '-'.join([str(v) for v in box])

            if 'scale_filter' in kwargs:
                try:
                    scale_filter = getattr(PIL.Image, kwargs['scale_filter'].upper())
                    label += f'f{scale_filter}'
                except AttributeError as error:
                    raise ValueError(
                        f"Invalid scale_filter value '{kwargs['scale_filter']}'") from error
            else:
                scale_filter = PIL.Image.LANCZOS
            return size, (label,
                          lambda image: image.resize(size=size,
                                                     box=box,
                                                     resample=scale_filter))
        return size, None

    def _render(self, path, operations: typing.List[typing.Callable], out_args):
        image = self._image

        with self._lock:
            if os.path.isfile(path):
                # file already exists
                return

            LOGGER.info("Rendering file %s", path)

            try:
                os.makedirs(os.path.dirname(path))
            except FileExistsError:
                pass

            try:
                for operation in operations:
                    image = operation(image)

                _, ext = os.path.splitext(path)
                with atomic_write(path, mode='w+b', suffix=ext, overwrite=True) as file:
                    image.save(file, **out_args)

                LOGGER.info("%s: complete", path)
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Failed to render %s -> %s",
                                 self._record.file_path, path)

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
        out_rel_path, size, pending = self._get_rendition(output_scale, False, **kwargs)

        if pending:
            signer = itsdangerous.URLSafeSerializer(flask.current_app.secret_key)
            return flask.url_for(
                'async',
                render_spec=signer.dumps(
                    (self._record.file_path, output_scale,
                     {k: v for k, v in kwargs.items() if k in RENDITION_ARG_FILTER})),
                _external=kwargs.get('absolute')), size
        return utils.static_url(out_rel_path, kwargs.get('absolute')), size

    def render_async(self, output_scale, **kwargs):
        """ Initiate the rendering of an image """
        out_rel_path, size, pending = self._get_rendition(output_scale, True, **kwargs)
        return utils.static_url(out_rel_path, kwargs.get('absolute')), size, pending

    @cached_property
    def _image(self):
        with self._lock:
            image = PIL.Image.open(self._record.file_path)

        return image

    def get_rendition_size(self, spec, output_scale, crop) -> SizeSpecType:
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

        if mode == 'fill':
            return self._get_rendition_fill_size(spec, width, height, output_scale)

        if mode == 'fit':
            return self._get_rendition_fit_size(spec, width, height, output_scale)

        if mode == 'stretch':
            return self._get_rendition_stretch_size(spec, width, height, output_scale)

        raise ValueError(f"Unknown resize mode {mode}")

    @staticmethod
    def _get_rendition_fit_size(spec, input_w, input_h, output_scale) -> SizeSpecType:
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
    def _get_rendition_fill_size(spec, input_w, input_h, output_scale) -> SizeSpecType:
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
    def _get_rendition_stretch_size(spec, input_w, input_h, output_scale) -> SizeSpecType:
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
            if isinstance(bgcolor, list):
                bgcolor = tuple(bgcolor)
            background = PIL.Image.new('RGB', image.size, bgcolor)
            background.paste(image, mask=image.split()[3])
            image = background

        return image.convert('RGB')

    def _get_renditions(self, kwargs):
        """ Get a bunch of renditions; returns a tuple of 1x, 2x, size """
        img_1x, size = self.get_rendition(
            1, **utils.remap_args(kwargs, {"quality": "quality_ldpi"}))
        img_2x, _ = self.get_rendition(
            2, **utils.remap_args(kwargs, {"quality": "quality_hdpi"}))

        return (img_1x, img_2x, size)

    def _get_img_attrs(self, spec, style_parts):
        """ Get the attributes of an an <img> tag for this image, hidpi-aware """
        # pylint:disable=unused-argument

        # Get the 1x and 2x renditions
        img_1x, img_2x, size = self._get_renditions(spec)

        attrs = {
            'src': img_1x,
            'width': size[0],
            'height': size[1]
        }

        if img_1x != img_2x:
            attrs['srcset'] = f"{img_1x} 1x, {img_2x} 2x"

        return attrs

    def _css_background(self, **kwargs):
        """ Get the CSS specifiers for this as a hidpi-capable background image """

        # Get the 1x and 2x renditions
        img_1x, img_2x, _ = self._get_renditions(kwargs)

        tmpl = f'background-image: url("{img_1x}");'
        if img_2x and img_1x != img_2x:
            tmpl += f'background-image: image-set(url("{img_1x}") 1x, url("{img_2x}") 2x);'
        return tmpl

    @staticmethod
    def clean_cache(max_age):
        """ Clean the rendition cache of files older than max_age seconds """
        cache_dir = os.path.join(config.static_folder,
                                 config.image_output_subdir)
        return LocalImage.thread_pool().submit(LocalImage._clean_cache, max_age, cache_dir)

    @staticmethod
    def _clean_cache(max_age, cache_dir: str):
        threshold = time.time() - max_age
        LOGGER.debug("Deleting image renditions older than %d from %s", threshold,
                     cache_dir)

        # delete expired files
        for root, _, files in os.walk(cache_dir):
            for file in files:
                try:
                    path = os.path.join(root, file)
                    mtime = os.stat(path).st_mtime
                    LOGGER.debug("checking %s (%d)", path, mtime)
                    if os.path.isfile(path) and mtime < threshold:
                        os.unlink(path)
                        LOGGER.info("Expired stale rendition %s (mtime=%d threshold=%d)",
                                    path, mtime, threshold)
                except FileNotFoundError:
                    pass
            if next(os.scandir(root), None) is None:
                try:
                    os.removedirs(root)
                    LOGGER.info("Removed empty cache directory %s", root)
                except OSError:
                    LOGGER.exception("Couldn't remove %s", root)
