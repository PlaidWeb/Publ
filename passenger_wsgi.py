#!env/bin/python
# Wrapper script to make this work in Passenger environments (e.g. Dreamhost)

import sys
import os
import subprocess
import logging
import logging.handlers

logging.basicConfig(level=logging.INFO)

# set up logging; see
# https://docs.python.org/2/library/logging.config.html#logging-config-fileformat
# for details
if os.path.isfile('logging.conf'):
    logging.config.fileConfig('logging.conf')
else:
    # This needs to be compatible with both python2 and python3, so unfortunately
    # we can't just use logging.basicConfig(handlers=...)
    log_handler = logging.handlers.TimedRotatingFileHandler('tmp/publ.log')
    log_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s '
        '[in %(pathname)s:%(lineno)d]'
    ))
    log_handler.setLevel(logging.INFO)
    logging.getLogger().addHandler(log_handler)

logger = logging.getLogger(__name__)

logger.info('My interpreter: %s' % sys.executable)

INTERP = subprocess.check_output(
    ['pipenv', 'run', 'which', 'python3']).strip().decode('utf-8')

if sys.executable != INTERP:
    logger.info('Restarting with interpreter: %s', INTERP)
    [h.flush() for h in logger.handlers]
    os.execl(INTERP, INTERP, *sys.argv)

sys.path.append(os.getcwd())

# load the app
import main


# hackish way to make Passenger urldecode the same way WSGI does
import urllib.parse


def application(environ, start_response):
    """
        make Passenger interpret PATH_INFO the same way that the WSGI standard
        does
    """

    environ["PATH_INFO"] = urllib.parse.unquote(environ["PATH_INFO"])
    return main.app(environ, start_response)

# Uncomment next two lines to enable debugging
# from werkzeug.debug import DebuggedApplication
# application = DebuggedApplication(application, evalex=True)
