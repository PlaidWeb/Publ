""" Handlers for images and files """

import errno
import hashlib
import html
import io
import itertools
import logging
import os
import random
import re
import time
import typing

import flask
import itsdangerous
import PIL.Image
import werkzeug.exceptions as http_error
from pony import orm

from .. import model, utils
from ..config import config
from .external import ExternalImage
from .image import Image
from .local import LocalImage, fix_orientation

LOGGER = logging.getLogger(__name__)

# Bump this if any defaults or processing changes
RENDITION_VERSION = 1


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

    def _get_img_attrs(self, spec, style_parts):
        # pylint:disable=unused-argument
        raise FileNotFoundError(
            errno.ENOENT, os.strerror(errno.ENOENT), self.path)

    def _css_background(self, **kwargs):
        return f'/* not found: {self.path} */'

    @property
    def _filename(self):
        return os.path.basename(self.path)


@orm.db_session
def _get_asset(file_path):
    """ Get the database record for an asset file """
    record = model.Image.get(file_path=file_path)
    fingerprint = ','.join((utils.file_fingerprint(file_path),
                            str(RENDITION_VERSION)))
    if not record or record.fingerprint != fingerprint:
        # Reindex the file
        LOGGER.info("Updating image %s -> %s", file_path, fingerprint)

        # compute the md5sum; from https://stackoverflow.com/a/3431838/318857
        md5 = hashlib.md5()
        md5.update(bytes(RENDITION_VERSION))
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
            image = fix_orientation(image)
        except IOError:
            image = None

        if image:
            values.update({
                'width': image.width,
                'height': image.height,
                'transparent': image.mode in ('RGBA', 'P'),
                'is_asset': False,
            })
        else:
            # PIL could not figure out what file type this is, so treat it as
            # an asset
            values.update({
                'is_asset': True,
                'asset_name': os.path.join(values['checksum'][:5],
                                           os.path.basename(file_path)),
            })
        record = model.Image.get(file_path=file_path)
        if record:
            record.set(**values)
        else:
            record = model.Image(**values)
        orm.commit()

    return record


def get_image(path: str, search_path: typing.Union[str, utils.ListLike[str]]) -> Image:
    """ Get an Image object. If the path is given as absolute, it will be
    relative to the content directory; otherwise it will be relative to the
    search path.

    path -- the image's filename
    search_path -- a search path for the image (string or list of strings)
    """
    search_path = tuple(utils.as_list(search_path))

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


def parse_img_config(text: str) -> typing.Tuple[str, utils.ArgDict]:
    """ Parses an arglist into arguments for Image, as a kwargs dict """

    text, pos_args, kwargs = utils.parse_spec(text, 2)

    if len(pos_args) >= 1:
        if 'width' in kwargs:
            raise TypeError("Got multiple values for width")
        kwargs['width'] = int(pos_args[0])
    if len(pos_args) >= 2:
        if 'height' in kwargs:
            raise TypeError("Got multiple values for height")
        kwargs['height'] = int(pos_args[1])

    return text, kwargs


def parse_image_spec(path: str) -> typing.Tuple[str, utils.ArgDict, typing.Optional[str]]:
    """ Parses out a Publ-Markdown image spec into a tuple of path, args, title """

    title: typing.Optional[str] = None

    # Parse out the title..
    match = re.match(r'(.+)\s+\"(.*)\"\s*$', path)
    if match:
        path, title = match.group(1, 2)

    path, args = parse_img_config(path)

    return path, args, (title and html.unescape(title))


def get_spec_list(image_specs: str, container_args: utils.ArgDict):
    """ Given a list of specs and a set of container args, return a list of
    tuples of (image_spec,bool), where the bool indicates whether the image
    is visible. """

    spec_list = [spec.strip() for spec in image_specs.split('|')]

    if 'count' in container_args:
        count, offset = container_args['count'], container_args.get('count_offset', 0)
        first, last = offset, offset + count
        return list(itertools.chain(zip(spec_list[:first], itertools.repeat(False)),
                                    zip(spec_list[first:last], itertools.repeat(True)),
                                    zip(spec_list[last:], itertools.repeat(False))))

    return zip(spec_list, itertools.repeat(True))


def clean_cache(max_age: float):
    """ Clean the rendition cache of renditions which haven't been accessed in a while

    :param max_age: the TTL on a rendition, in seconds
    """

    return LocalImage.clean_cache(max_age)


def get_async(render_spec: str):
    """ Quasi-asynchronously fetch an image that needs to be rendered """

    try:
        # Get the image request parameters
        file_path, output_scale, args = itsdangerous.URLSafeSerializer(
            flask.current_app.secret_key).loads(render_spec)
    except itsdangerous.BadData as error:
        raise http_error.BadRequest(f"Invalid image request: {error}")

    try:
        asset = _get_asset(file_path)
        if not asset:
            raise http_error.NotFound(f"File not found: {file_path}")
        renderer = LocalImage(asset, [])
        output_path, _, pending = renderer.render_async(output_scale, **args)
    except FileNotFoundError as err:
        raise http_error.NotFound(f"File not found: {file_path}") from err

    LOGGER.debug("Request for %s (%d) %s -> %s pending=%s", file_path, output_scale, args,
                 output_path, pending)

    if not pending:
        return flask.redirect(output_path)

    retry_count = int(flask.request.args.get('retry_count', 0))
    if retry_count < 10:
        time.sleep(0.25)  # ghastly hack to get the client to backoff a bit
        return flask.redirect(flask.url_for('async',
                                            render_spec=render_spec,
                                            cb=random.randint(0, 2**48),
                                            retry_count=retry_count + 1))

    return make_placeholder(output_path)


def make_placeholder(output_path: str):
    """ Generate a placeholder image for the given file path """
    vals = [int(b) for b in hashlib.md5(
        output_path.encode('utf-8')).digest()[0:12]]
    placeholder = PIL.Image.new('RGB', (2, 2))
    placeholder.putdata(list(zip(vals[0::3], vals[1::3], vals[2::3])))
    outbytes = io.BytesIO()
    placeholder.save(outbytes, "PNG")
    outbytes.seek(0)

    response = flask.make_response(
        flask.send_file(outbytes, mimetype='image/png'))
    response.headers['Refresh'] = 5
    return response
