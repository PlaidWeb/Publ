# config.py
""" configuration container for Publ """

import os
import sys
import typing

from dateutil import tz

# pylint: disable=invalid-name

database_config = {
    'provider': 'sqlite',
    'filename': ':memory:'
}
index_rescan_interval = 7200

# Site content locations
content_folder = 'content'
template_folder = 'templates'
static_folder = 'static'
static_url_path = '/static'

# Image rendition cache
image_output_subdir = '_img'
image_cache_interval = 3600
image_cache_age = 86400 * 30  # one month
image_render_threads = os.cpu_count()

timezone = tz.tzlocal()

# Page rendering
cache: typing.Dict[str, str] = {}
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
auth: typing.Dict[str, str] = {}
user_list = 'users.cfg'
admin_group = 'admin'
auth_log_prune_interval = 3600
auth_log_prune_age = 86400 * 30  # one month
max_token_age = 3600


def setup(cfg):
    """ set up the global configuration from an object """

    # copy the necessary configuration values over
    this_module = sys.modules[__name__]
    for name, value in cfg.items():
        if hasattr(this_module, name):
            setattr(this_module, name, value)
