#!/usr/bin/env python

from flask import Flask
from flask_testing import TestCase
import jinja2
import yaml, json
import re
from swagger_spec_validator.validator20 import validate_spec
import test.stubs
import logging

import apiserver.apiserver as apiserver

class BaseTest(TestCase):
    def setUp(self):
        #logging.basicConfig(level=logging.DEBUG)
        self.db = test.stubs.testDB()
        self.db.test_add_cid(10, append=False, state=self.db.STATE_DONE)
        self.db.test_add_cid(20, state=self.db.STATE_DONE)
        self.db.test_add_cid(30)

        apiserver.api.app = apiserver.app
        apiserver.app.db = self.db

    def create_app(self):
        return apiserver.app.app

    def validate_iso8601_ts(self, ts):
        # YYYY-MM-DDTHH:MM:SS.mmmmmm+HH:MM or, if microsecond is 0 YYYY-MM-DDTHH:MM:SS+HH:MM
        return re.match(r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d{6})?[+-]\d\d:\d\d$', ts)

    def assert_iso8601_ts(self, ts):
        self.assertTrue(self.validate_iso8601_ts(ts))

class BasicTest(BaseTest):
    def test_iso8601(self):
        self.assertTrue(self.validate_iso8601_ts('2017-04-27T08:00:00.123456+01:00'))
        self.assertTrue(self.validate_iso8601_ts('2017-04-27T08:00:00+01:00'))
        # Some bogus formats
        self.assertFalse(self.validate_iso8601_ts('2017-04-27T08:00:00.12345678+01:00'))
        self.assertFalse(self.validate_iso8601_ts('2017-04-27T08:00:00+01:000'))
        self.assertFalse(self.validate_iso8601_ts('2017:04:27T08:00:00.123456+01:00'))
        self.assertFalse(self.validate_iso8601_ts('2017/04/27T08:00:00+01:00'))

class TestApi(BaseTest):
    def test_spec(self):
        specification = 'apiserver/apispec.yaml'

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

class ApiServerTest(BaseTest):
    def test_error404(self):
        resp = self.client.get('/api/0.1/nonexistent')
        self.assertEqual(resp.status_code, 404)

    def test_get_changesets(self):
        resp = self.client.get('/api/v0.1/changesets')
        self.assertEqual(resp.status_code, 200)
        csets = json.loads(resp.get_data())
        logging.debug('Got csets={}'.format(csets))
        self.assert_iso8601_ts(csets['timestamp'])
        csets = csets['changesets']
        self.assertEqual(3, len(csets))
        self.assertEqual(10, csets[0]['cid'])
        self.assert_iso8601_ts(csets[0]['updated'])

    def test_get_changesets_w_limit(self):
        resp = self.client.get('/api/v0.1/changesets?limit=2')
        self.assertEqual(resp.status_code, 200)
        csets = json.loads(resp.get_data())
        csets = csets['changesets']
        self.assertEqual(2, len(csets))

        resp = self.client.get('/api/v0.1/changesets?limit=4')
        self.assertEqual(resp.status_code, 200)
        csets = json.loads(resp.get_data())
        csets = csets['changesets']
        self.assertEqual(3, len(csets))


    def test_get_changesets_filter_state(self):
        resp = self.client.get('/api/v0.1/changesets?state=DONE')
        self.assertEqual(resp.status_code, 200)
        csets = json.loads(resp.get_data())
        csets = csets['changesets']
        self.assertEqual(2, len(csets))

        resp = self.client.get('/api/v0.1/changesets?state=NEW')
        self.assertEqual(resp.status_code, 200)
        csets = json.loads(resp.get_data())
        csets = csets['changesets']
        self.assertEqual(1, len(csets))
        self.assertEqual(30, csets[0]['cid'])

    def test_get_changeset(self):
        resp = self.client.get('/api/v0.1/changeset/10')
        self.assertEqual(resp.status_code, 200)
        cset = json.loads(resp.get_data())
        logging.debug('Got cset={}'.format(cset))
        self.assertEqual(10, cset['cid'])
        self.assert_iso8601_ts(cset['updated'])
        self.assert_iso8601_ts(cset['refreshed'])
        self.assert_iso8601_ts(cset['state_changed'])
        self.assert_iso8601_ts(cset['queued'])
        self.assert_iso8601_ts(cset['source']['observed'])

    def test_get_changeset_error404(self):
        resp = self.client.get('/api/v0.1/changeset/10000')
        self.assertEqual(resp.status_code, 404)

if __name__ == '__main__':
    unittest.main()
