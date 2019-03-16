#!/usr/bin/env python

import os
import unittest
import mock
from mock import patch, call
import logging
import osmtracker
import db
import stubs
import osm.test.stubs
import datetime, pytz
import pprint

logger = logging.getLogger('')
cwd = os.path.dirname(os.path.abspath(__file__))+'/'

class BaseTest(unittest.TestCase, stubs.FileWriter_Mixin):
    def setUp(self):
        #logging.basicConfig(level=logging.DEBUG)
        self.db = stubs.testDB()
        self.cfg = stubs.testConfig()
        self.osmapi = osm.test.stubs.testOsmApi(datapath=cwd+'../osm/test/data')
        self.requests = osm.test.stubs.testRequests(datapath=cwd+'../osm/test/data',
                                                    sigint_on=[])

class TestSigInt(BaseTest):

    @patch('osm.diff.requests.get')
    def test_diff_fetch(self, UrlGet):
        UrlGet.side_effect = self.requests.get

        # oldptr = self.db.pointer['seqno']
        # osmtracker.diff_fetch(None, self.cfg, self.db)
        # newptr = self.db.pointer['seqno']
        # self.assertEqual(oldptr+1, newptr)
        #print 'OsmDiffApi calls:', OsmDiffApi.mock_calls

        self.requests.sigint_on = ['get']
        oldptr = self.db.pointer['seqno']
        self.assertRaises(KeyboardInterrupt, osmtracker.diff_fetch, None, self.cfg, self.db)
        newptr = self.db.pointer['seqno']
        self.assertEqual(oldptr, newptr)

    @patch('osm.poly.Poly')
    @patch('osm.diff.requests.get')
    @patch('osm.changeset.OsmApi')
    def test_cset_filter(self, OsmApi, UrlGet, Poly):
        UrlGet.side_effect = self.requests.get
        OsmApi.return_value = self.osmapi
        Poly.return_value.contains_bbox.return_value = True
        self.db.test_add_cid(10, state=self.db.STATE_NEW, append=False)

        self.osmapi.sigint_on = ['ChangesetGet']
        self.assertRaises(KeyboardInterrupt, osmtracker.cset_filter, self.cfg, self.db, {'cid': 10, 'source': {'sequenceno': 20000}})
        self.assertEqual(self.db.csets[0]['state'], self.db.STATE_NEW)

    @patch('osm.diff.requests.get')
    @patch('osm.changeset.OsmApi')
    def test_cset_analyse(self, OsmApi, UrlGet):
        UrlGet.side_effect = self.requests.get
        OsmApi.return_value = self.osmapi
        self.db.test_add_cid(10, state=self.db.STATE_BOUNDS_CHECKED, append=False)

        self.db.sigint_on = ['chgset_get_meta']
        self.osmapi.sigint_on = ['ChangesetGet']
        self.assertRaises(KeyboardInterrupt, osmtracker.csets_analyse_initial, self.cfg, self.db, {'cid': 10, 'source': {'sequenceno': 20000}})
        self.assertEqual(self.db.csets[0]['state'], self.db.STATE_BOUNDS_CHECKED)

    @patch('osm.poly.Poly')
    @patch('osm.diff.requests.get')
    @patch('osm.changeset.OsmApi')
    def test_worker(self, OsmApi, UrlGet, Poly):
        UrlGet.side_effect = self.requests.get
        OsmApi.return_value = self.osmapi
        Poly.return_value.contains_bbox.return_value = True
        self.db.test_add_cid(10, append=False)

        self.db.sigint_on = ['chgset_get_meta']
        self.osmapi.sigint_on = ['ChangesetGet']
        self.assertRaises(KeyboardInterrupt, osmtracker.cset_filter, self.cfg, self.db, {'cid': 10, 'source': {'sequenceno': 20000}})
        self.assertEqual(self.db.csets[0]['state'], self.db.STATE_NEW)

if __name__ == '__main__':
    unittest.main()
