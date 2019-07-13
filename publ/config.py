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

# Site content locations
content_folder = 'content'
template_folder = 'templates'
static_folder = 'static'
static_url_path = '/static'

# Image rendition cache
image_output_subdir = '_img'
index_rescan_interval = 7200
image_cache_interval = 3600
image_cache_age = 86400 * 30  # one month

timezone = tz.tzlocal()

# Page rendering
cache = {}
markdown_extensions = (
    'tables',
    'fenced-code',
    'footnotes',
    'strikethrough',
    'highlight',
    'superscript',
    'math',
)

# Authentication
secret_key = str(uuid.uuid4())
auth = {}
user_list = 'users.cfg'
admin_group = 'admin'


def setup(cfg):
    """ set up the global configuration from an object """

    # copy the necessary configuration values over
    this_module = sys.modules[__name__]
    for name, value in cfg.items():
        if hasattr(this_module, name):
            setattr(this_module, name, value)
