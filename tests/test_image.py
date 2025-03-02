""" Tests of image-related functionality """

import logging
import os
import os.path
import tempfile
import time

import publ.image

from . import PublMock

LOGGER = logging.getLogger(__name__)


def test_clean_cache():
    """ Test the rendition cache cleanup """
    now = time.time()
    with tempfile.TemporaryDirectory() as tempdir:
        app = PublMock({
            'static_folder': tempdir,
            'image_output_subdir': 'images'
        })

        def get_path(*path) -> str:
            return os.path.join(tempdir, 'images', *path)

        def make_file(prefix, name, age) -> str:
            os.makedirs(get_path(prefix), exist_ok=True)
            path = os.path.join(get_path(prefix, name))
            with open(path, 'w', encoding='utf8') as out:
                out.write('name')
            os.utime(path, (now - age, now - age))
            LOGGER.info("%d: Created file %s with mtime %d", now, path, os.stat(path).st_mtime)
            return path

        make_file('foo', 'asdf', 86400)
        make_file('foo', 'poiu', 3600)
        make_file('bar', 'qwer', 86400)

        LOGGER.debug("tempdir contents before purge:")
        for (path, _, files) in os.walk(tempdir):
            LOGGER.debug("%s / %s", path, files)

        assert os.path.isfile(get_path('foo', 'asdf'))
        assert os.path.isfile(get_path('foo', 'poiu'))
        assert os.path.isfile(get_path('bar', 'qwer'))

        with app.app_context():
            publ.image.clean_cache(7200)

        LOGGER.debug("tempdir contents after purge:")
        for (path, _, files) in os.walk(tempdir):
            LOGGER.debug("%s / %s", path, files)

        assert not os.path.exists(get_path('foo', 'asdf'))
        assert os.path.isfile(get_path('foo', 'poiu'))
        assert not os.path.exists(get_path('bar', 'qwer'))
        assert not os.path.exists(get_path('bar'))
