import os
import time
import io

import flask
import PIL.Image

from . import config


def image(filename):
    """ Asynchronously fetch an image """

    if os.path.isfile(os.path.join(config.static_folder, filename)):
        return flask.redirect(flask.url_for('static', filename=filename))

    retry_count = int(flask.request.args.get('retry_count', 0))
    if retry_count < 3:
        time.sleep(0.5)  # ghastly hack
        return flask.redirect(flask.url_for('async', filename=filename, retry_count=retry_count + 1))

    # the image isn't available yet; generate a placeholder and let the
    # client attempt to re-fetch periodically, maybe
    vals = [int(b) for b in hashlib.md5(
        filename.encode('utf-8')).digest()[0:12]]
    placeholder = PIL.Image.new('RGB', (2, 2))
    placeholder.putdata(list(zip(vals[0::3], vals[1::3], vals[2::3])))
    outbytes = io.BytesIO()
    placeholder.save(outbytes, "PNG")
    outbytes.seek(0)
    return flask.send_file(outbytes, mimetype='image/png')
