""" Handlers for images and files """

import os
import hashlib
import logging
import re
import ast
import time
import random
import io
import errno
import html

from pony import orm
import flask
import PIL.Image

from .. import config
from .. import model, utils
from .external import ExternalImage
from .image import Image
from .local import LocalImage, fix_orientation

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name

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

    def _get_img_attrs(self, kwargs, style_parts):
        # pylint:disable=unused-argument
        raise FileNotFoundError(
            errno.ENOENT, os.strerror(errno.ENOENT), self.path)

    def _css_background(self, **kwargs):
        return '/* not found: {} */'.format(self.path)


@orm.db_session(immediate=True)
def _get_asset(file_path):
    """ Get the database record for an asset file """
    record = model.Image.get(file_path=file_path)
    fingerprint = ','.join((utils.file_fingerprint(file_path),
                            str(RENDITION_VERSION)))
    if not record or record.fingerprint != fingerprint:
        # Reindex the file
        logger.info("Updating image %s -> %s", file_path, fingerprint)

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
