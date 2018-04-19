# image.py
''' Managing image renditions '''

from __future__ import absolute_import, with_statement

import os
import math
import hashlib
import logging

import PIL.Image

from . import config
from . import model, utils

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


class Image:
    """ The basic Image class, which knows about the base version and how to
    generate renditions from it """

    def __init__(self, record):
        """ Get the base image from an index record """
        self._record = record

    def get_rendition(self, output_scale, kwargs):
        """
        Get the rendition for this image, generating it if necessary.
        Returns a tuple of `(relative_path, width, height)`, where relative_path
        is relative to the static file directory (i.e. what one would pass into
        `get_static()`)

        output_scale -- the upsample factor for the requested rendition

        Keyword arguments:

        scale -- the downsample factor for the base rendition
        max_width -- the maximum width to target for input_scale
        max_height -- the maximum height to target for input_scale
        scale_min_width -- the minimum width to target for input_scale
        scale_min_height -- the minimum height to target for input_scale
        """

        input_filename = self._record.file_path
        basename, ext = os.path.splitext(os.path.basename(input_filename))
        basename = utils.make_slug(basename)

        # The spec for building the output filename
        out_spec = [basename, self._record.checksum]

        width, height = self.get_rendition_fit_size(
            self._record, kwargs, output_scale)
        out_spec.append('{}x{}'.format(width, height))

        # Build the output filename
        out_basename = '_'.join([str(s) for s in out_spec]) + ext
        out_rel_path = os.path.join(
            config.image_output_subdir, out_basename)
        out_fullpath = os.path.join(config.static_folder, out_rel_path)
        out_dir = os.path.dirname(out_fullpath)

        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)

        if os.path.isfile(out_fullpath):
            # File already exists
            return out_rel_path, width, height

        # Process the file
        input_image = PIL.Image.open(input_filename)
        if width < self._record.width or height < self._record.height:
            input_image = input_image.resize(size=(width, height),
                                             resample=PIL.Image.LANCZOS)
        input_image.save(out_fullpath)
        return out_rel_path, width, height

    @staticmethod
    def get_rendition_fit_size(record, spec, output_scale):
        """ Determine the scaled size based on the provided spec """

        width = record.width
        height = record.height

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

        tgt_height = spec.get('height')
        if tgt_height and height > tgt_height:
            width = width * tgt_height / height
            height = tgt_height

        tgt_width, tgt_height = spec.get('max_width'), spec.get('max_height')

        if tgt_width and width > tgt_width:
            height = height * tgt_width / width
            width = tgt_width

        tgt_height = spec.get('height')
        if tgt_height and height > tgt_height:
            width = width * tgt_height / height
            height = tgt_height

        width = width * output_scale
        height = height * output_scale

        # Never scale to larger than the base rendition
        width = min(int(math.floor(width + 0.5)), record.width)
        height = min(int(math.floor(height + 0.5)), record.height)

        return width, height


def get_image(path, search_path):
    """ Get an Image object. Arguments:

    path -- the image's filename
    search_path -- a search path or list of search paths
    """

    file_path = utils.find_file(path, search_path)
    if not file_path:
        return None

    record = model.Image.get_or_none(file_path=file_path)
    mtime = os.stat(file_path).st_mtime
    if not record or record.mtime < mtime:
        # Reindex the file
        logger.info("Updating image %s", file_path)

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
            'mtime': mtime
        }
        record, created = model.Image.get_or_create(
            file_path=file_path, defaults=values)
        if not created:
            record.update(**values).where(model.Image.id == record.id)

    return Image(record)
