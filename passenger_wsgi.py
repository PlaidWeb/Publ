#!env/bin/python
# Wrapper script to make this work in Passenger environments (e.g. Dreamhost)

import sys, os
import subprocess
import logging
import logging.handlers

logger = logging.getLogger(__name__)

log_handler = logging.handlers.TimedRotatingFileHandler('tmp/passenger.log')
log_handler.setLevel(logging.DEBUG)
log_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s '
    '[in %(pathname)s:%(lineno)d]'
))
logger.addHandler(log_handler)

logger.info('My interpreter: %s' % sys.executable)

INTERP = subprocess.check_output(['pipenv', 'run', 'which', 'python3']).strip().decode('utf-8')
logger.info('Expected interpreter: %s' % INTERP)

if sys.executable != INTERP:
    log_handler.flush()
    os.execl(INTERP, INTERP, *sys.argv)

sys.path.append(os.getcwd())

import main

# hackish way to make Passenger urldecode the same way WSGI does
import urllib.parse
def application(environ, start_response):
    environ["PATH_INFO"] = urllib.parse.unquote(environ["PATH_INFO"])
    return main.app(environ, start_response)

# Uncomment next two lines to enable debugging
# from werkzeug.debug import DebuggedApplication
# application = DebuggedApplication(application, evalex=True)
