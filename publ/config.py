# config.py
""" configuration container for Publ """

import sys
from dateutil import tz

# pylint: disable=invalid-name

database = 'sqlite:///:memory:'
content_folder = 'content'
template_folder = 'templates'
static_folder = 'static'
static_url_path = '/static'
image_output_subdir = '_img'
index_rescan_interval = 7200
timezone = tz.tzlocal()
cache = {}


def setup(cfg):
    """ set up the global configuration from an object """

    # copy the necessary configuration values over
    this_module = sys.modules[__name__]
    for name, value in cfg.items():
        if hasattr(this_module, name):
            setattr(this_module, name, value)
