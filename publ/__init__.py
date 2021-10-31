""" Publ: A Flask-based site management system.

Like a static publishing system, but dynamic! See http://publ.beesbuzz.biz
for more information. """

import logging

from .flask_wrapper import Publ

LOGGER = logging.getLogger(__name__)


def publ(name, cfg):
    """ Legacy function that originally did a lot more """
    LOGGER.warning("This function is deprecated; use publ.Publ instead")
    return Publ(name, cfg)
