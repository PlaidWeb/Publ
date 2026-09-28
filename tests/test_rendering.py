""" Tests of rendering functions """

import os.path

import flask
import pytest

import publ

from .test_app import app


def test_etag_caching():
    """ Test that ETags work the way they're supposed to """

    # test index pages
    with app.test_client() as client:
        # Get the base ETag
        response = client.get('/')
        etag = response.headers['ETag']

        # Make sure ETag returns a cache hit
        response = client.get('/', headers={'If-None-Match': etag})
        assert response.status_code == 304

        # Make sure weak ETag returns a cache hit
        response = client.get('/', headers={'If-None-Match': f'W/{etag}'})
        assert response.status_code == 304

        # Make sure the wrong ETag is a cache miss
        response = client.get('/', headers={'If-None-Match': '"FAKE ETAG"'})
        assert response.status_code == 200

        # Make sure etags are different across pages
        response = client.get('/caching/', headers={'If-None-Match': etag})
        assert response.status_code == 200
        assert response.headers['ETag'] != etag

        # Accept multiple ETags as long as one matches
        response = client.get('/', headers={'If-None_match': f'{etag}, "FAKE ETAG'})
        assert response.status_code == 304

    # test entry pages
    with app.test_client() as client:
        # Get the base ETag
        response = client.get('/308-This-is-a-simple-test-entry')
        etag = response.headers['ETag']

        # Make sure ETag returns a cache hit
        response = client.get('/308-This-is-a-simple-test-entry', headers={'If-None-Match': etag})
        assert response.status_code == 304

        # Make sure weak ETag returns a cache hit
        response = client.get('/308-This-is-a-simple-test-entry',
                              headers={'If-None-Match': f'W/{etag}'})
        assert response.status_code == 304

        # Make sure the wrong ETag is a cache miss
        response = client.get('/308-This-is-a-simple-test-entry',
                              headers={'If-None-Match': '"FAKE ETAG"'})
        assert response.status_code == 200

        # Make sure etags are different across pages
        response = client.get('/caching/969-caching-manual-smoke-test',
                              headers={'If-None-Match': etag})
        assert response.status_code == 200
        assert response.headers['ETag'] != etag

        # Accept multiple ETags as long as one matches
        response = client.get('/308-This-is-a-simple-test-entry',
                              headers={'If-None_match': f'{etag}, "FAKE ETAG'})
        assert response.status_code == 304

def test_retry_after():
    """ Ensure that the retry_after header propagates """
    with app.test_client() as client:
        response = client.get('/_retry')
        assert response.headers['retry-after'] == '3600'
