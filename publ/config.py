# config.py
""" configuration container for Publ """

import sys
import uuid
from dateutil import tz

# pylint: disable=invalid-name

database_config = {
    'provider': 'sqlite',
    'filename': ':memory:'
}

content_folder = 'content'
template_folder = 'templates'
static_folder = 'static'
static_url_path = '/static'
image_output_subdir = '_img'
index_rescan_interval = 7200
image_cache_interval = 3600
image_cache_age = 86400 * 30  # one month
cache = {}
timezone = tz.tzlocal()
markdown_extensions = (
    'tables', 'fenced-code', 'footnotes', 'strikethrough', 'highlight', 'superscript', 'math',
)
secret_key = uuid.uuid4()
auth = {}


def setup(cfg):
    """ set up the global configuration from an object """

    # copy the necessary configuration values over
    this_module = sys.modules[__name__]
    for name, value in cfg.items():
        if hasattr(this_module, name):
            setattr(this_module, name, value)
