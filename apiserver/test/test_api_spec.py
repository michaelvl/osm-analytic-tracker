#!/usr/bin/env python

import pytest
import connexion
import flask
import jinja2
import yaml, json
import re
from swagger_spec_validator.validator20 import validate_spec
import test.stubs
import logging

specification = '/osmtracker/apiserver/apispec.yaml'

app = connexion.FlaskApp(__name__)
app.add_api(specification)

def setup_db():
    #logging.basicConfig(level=logging.DEBUG)
    db = test.stubs.testDB()
    db.test_add_cid(10, append=False, state=db.STATE_DONE)
    db.test_add_cid(20, state=db.STATE_DONE)
    db.test_add_cid(30)
    return db

app.db = setup_db()

@pytest.fixture(scope='module')
def test_stub():
    with app.app.test_client() as c:
        with app.app.app_context():
            flask.g.app = app
            yield c

def get_app():
    return flask.current_app


def validate_iso8601_ts(ts):
    # YYYY-MM-DDTHH:MM:SS.mmmmmm+HH:MM or, if microsecond is 0 YYYY-MM-DDTHH:MM:SS+HH:MM
    return re.match(r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d{6})?[+-]\d\d:\d\d$', ts) != None

def assert_iso8601_ts(ts):
    assert validate_iso8601_ts(ts)

def test_iso8601(test_stub):
    assert validate_iso8601_ts('2017-04-27T08:00:00.123456+01:00')
    assert validate_iso8601_ts('2017-04-27T08:00:00+01:00')
    # Some bogus formats
    assert not validate_iso8601_ts('2017-04-27T08:00:00.12345678+01:00')
    assert not validate_iso8601_ts('2017-04-27T08:00:00+01:000')
    assert not validate_iso8601_ts('2017:04:27T08:00:00.123456+01:00')
    assert not validate_iso8601_ts('2017/04/27T08:00:00+01:00')

def test_spec(test_stub):
    with open(specification, 'rb') as f:
        args = {}
        spec_data = f.read()
        try:
            template = spec_data.decode()
        except UnicodeDecodeError:
            template = spec_data.decode('utf-8', 'replace')
    # If jinja2 templating/arguments are used...
    spec = jinja2.Template(template).render(**args)
    spec = yaml.safe_load(template)

    #pprint.pprint(spec)
    validate_spec(spec)


def test_error404(test_stub):
    resp = test_stub.get('/api/0.1/nonexistent')
    assert resp.status_code == 404


def test_get_changesets(test_stub):
    resp = test_stub.get('/api/v0.1/changesets')
    assert resp.status_code == 200
    csets = json.loads(resp.get_data())
    logging.debug('Got csets={}'.format(csets))
    assert_iso8601_ts(csets['timestamp'])
    csets = csets['changesets']
    assert len(csets) == 3
    assert csets[0]['cid'] == 10
    assert_iso8601_ts(csets[0]['updated'])

    
def test_get_changesets_w_limit(test_stub):
    resp = test_stub.get('/api/v0.1/changesets?limit=2')
    assert resp.status_code == 200
    csets = json.loads(resp.get_data())
    csets = csets['changesets']
    assert len(csets) == 2

    resp = test_stub.get('/api/v0.1/changesets?limit=4')
    assert resp.status_code == 200
    csets = json.loads(resp.get_data())
    csets = csets['changesets']
    assert len(csets) == 3


def test_get_changesets_filter_state(test_stub):
    resp = test_stub.get('/api/v0.1/changesets?state=DONE')
    assert resp.status_code == 200
    csets = json.loads(resp.get_data())
    csets = csets['changesets']
    assert len(csets) == 2

    resp = test_stub.get('/api/v0.1/changesets?state=NEW')
    assert resp.status_code == 200
    csets = json.loads(resp.get_data())
    csets = csets['changesets']
    assert len(csets) == 1
    assert csets[0]['cid'] == 30

def test_get_changeset(test_stub):
    resp = test_stub.get('/api/v0.1/changeset/10')
    assert resp.status_code == 200
    cset = json.loads(resp.get_data())
    logging.debug('Got cset={}'.format(cset))
    assert cset['cid'] == 10
    assert_iso8601_ts(cset['updated'])
    assert_iso8601_ts(cset['refreshed'])
    assert_iso8601_ts(cset['state_changed'])
    assert_iso8601_ts(cset['queued'])
    assert_iso8601_ts(cset['source']['observed'])

def test_get_changeset_error404(test_stub):
    resp = test_stub.get('/api/v0.1/changeset/10000')
    assert resp.status_code == 404
