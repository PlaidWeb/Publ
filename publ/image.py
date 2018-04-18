# image.py
''' Managing image renditions '''

import os
import math
import hashlib

import PIL
import config

from . import model, utils


class Image:
    """ The basic Image class, which knows about the base version and how to
    generate renditions from it """

    def __init__(self, record):
        """ Get the base image from an index record """
        self._record = record

    def get_rendition(self, **kwargs):
        """
        Get the rendition for this image, generating it if necessary.
        Returns a tuple of `(relative_path, width, height)`, where relative_path
        is relative to the static file directory (i.e. what one would pass into
        `get_static()`)

        Arguments:

        input_scale -- the downsample factor for the base rendition
        output_scale -- the upsample factor for the requested rendition
        max_width -- the maximum width to target for input_scale
        max_height -- the maximum height to target for input_scale
        scale_min_width -- the minimum width to target for input_scale
        scale_min_height -- the minimum height to target for input_scale
        """

        input_filename = self._record.file_path
        basename, ext = os.path.splitext(os.path.basename(input_filename))

        # The spec for building the output filename
        out_spec = [basename, self._record.checksum]

        width, height = self.get_rendition_fit_size(self._record, kwargs)
        out_spec.append('{}x{}'.format(width, height))

        # Build the output filename
        out_basename = '_'.join([str(s) for s in out_spec]) + ext
        out_rel_path = os.path.join(
            config.image_output_directory, out_basename)
        out_fullpath = os.path.join(config.static_directory, out_rel_path)
        out_dir = os.path.dirname(out_fullpath)

        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)

        if os.path.isfile(out_fullpath):
            # File already exists
            return out_rel_path

        # Process the file
        input_image = PIL.Image.open(input_filename)
        if width < self._record.width or height < self._record.height:
            input_image = input_image.resize(size=(width, height),
                                             resample=PIL.Image.LANCZOS)
        input_image.save(out_fullpath)
        return out_rel_path

    @staticmethod
    def get_rendition_fit_size(record, spec):
        """ Determine the scaled size based on the provided spec """

        width = record.width
        height = record.height

        scale = spec.get('input_scale')
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

        max_width = spec.get('max_width')
        if max_width and width > max_width:
            height = height * max_width / width
            width = max_width

        max_height = spec.get('max_width')
        if max_height and height > max_height:
            width = width * max_height / height
            height = max_height

        out_scale = spec.get('output_scale')
        if out_scale:
            width = width * out_scale
            height = height * out_scale

        # Never scale to larger than the base rendition
        width = min(int(math.floor(width + 0.5)), record.width)
        height = min(int(math.floor(height + 0.5)), record.height)

        return width, height


def get_image(path, relative_to):
    """ Get an Image object. Arguments:

    path -- the image's filename
    relative_to -- a search path or list of search paths
    """

    file_path = utils.find_file(path, relative_to)
    if not file_path:
        return None

    record = model.Image.get_or_none(file_path=file_path)
    mtime = os.stat(file_path).st_mtime
    if not record or record.mtime < mtime:
        # Reindex the file

        # compute the md5sum; from https://stackoverflow.com/a/3431838/318857
        md5 = hashlib.md5()
        with open(file_path, 'r') as file:
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
