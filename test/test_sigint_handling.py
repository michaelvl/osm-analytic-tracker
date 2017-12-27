#!/usr/bin/env python

import unittest
import mock
from mock import patch, call
import logging
import osmtracker
import db
import stubs
import osm.test.stubs
import datetime
import pprint

logger = logging.getLogger('')


class BaseTest(unittest.TestCase, stubs.FileWriter_Mixin):
    def setUp(self):
        #logging.basicConfig(level=logging.DEBUG)
        self.db = stubs.testDB()
        self.cfg = stubs.testConfig()
        self.osmapi = osm.test.stubs.testOsmApi(datapath='osm/test/data')
        self.requests = osm.test.stubs.testRequests(datapath='osm/test/data',
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

    @patch('osm.diff.requests.get')
    @patch('osm.changeset.OsmApi')
    def test_csets_filter(self, OsmApi, UrlGet):
        UrlGet.side_effect = self.requests.get
        OsmApi.return_value = self.osmapi
        self.db.test_add_cid(11, state=self.db.STATE_NEW, append=False)

        self.osmapi.sigint_on = ['ChangesetGet']
        self.assertRaises(KeyboardInterrupt, osmtracker.csets_filter, None, self.cfg, self.db)
        self.assertEqual(self.db.csets[0]['state'], self.db.STATE_NEW)

    @patch('osm.diff.requests.get')
    @patch('osm.changeset.OsmApi')
    def test_csets_analyze(self, OsmApi, UrlGet):
        UrlGet.side_effect = self.requests.get
        OsmApi.return_value = self.osmapi

        self.db.sigint_on = ['chgset_get_meta']
        self.osmapi.sigint_on = ['ChangesetGet']

        # TODO: csets_analyze_periodic_reprocess_open and csets_analyze_periodic_reprocess_closed not covered

        for state in [self.db.STATE_BOUNDS_CHECKED, self.db.STATE_CLOSED, self.db.STATE_OPEN]:
            self.db.test_add_cid(11, state=state, append=False)
            self.assertRaises(KeyboardInterrupt, osmtracker.csets_analyze, None, self.cfg, self.db)
            self.assertEqual(self.db.csets[0]['state'], state)

    @patch('osm.diff.requests.get')
    @patch('osm.changeset.OsmApi')
    def test_worker(self, OsmApi, UrlGet):
        UrlGet.side_effect = self.requests.get
        OsmApi.return_value = self.osmapi
        self.db.test_add_cid(10, append=False)

        self.db.sigint_on = ['chgset_get_meta']
        self.osmapi.sigint_on = ['ChangesetGet']
        self.assertRaises(KeyboardInterrupt, osmtracker.worker, None, self.cfg, self.db)
        self.assertEqual(self.db.csets[0]['state'], self.db.STATE_NEW)

if __name__ == '__main__':
    unittest.main()
