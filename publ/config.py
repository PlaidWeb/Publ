# config.py
""" configuration container for Publ """

import logging
import os
import typing

import werkzeug.local
from dateutil import tz
from flask import current_app

LOGGER = logging.getLogger(__name__)


class _Defaults:
    # pylint:disable=too-few-public-methods
    database_config = {
        'provider': 'sqlite',
        'filename': ':memory:'
    }
    index_rescan_interval = 7200
    index_wait_time = 1

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


class Config(_Defaults):
    """ Stores configuration for a Publ app """
    # pylint:disable=too-few-public-methods

    def __init__(self, from_dict):
        # Copy over the defaults
        for key, val in _Defaults.__dict__.items():
            if key[0] != '_':
                setattr(self, key, val)

        # Copy over the new configuration
        for key, val in from_dict.items():
            if hasattr(self, key):
                setattr(self, key, val)
            else:
                LOGGER.warning("Unknown configuration key %s", key)


config = werkzeug.local.LocalProxy(lambda: current_app.publ_config)  # pylint:disable=invalid-name
