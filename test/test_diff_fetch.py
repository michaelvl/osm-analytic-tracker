import os
import unittest
import mock
from mock import patch, call
import logging
import osmtracker
import db
import stubs
import osm.test.stubs
import osm.diff as osmdiff
import datetime
import pprint

logger = logging.getLogger('')
cwd = os.path.dirname(os.path.abspath(__file__))+'/'

class Args:
    def __init__(self):
        self.metrics = True
        self.track = False

class BaseTest(unittest.TestCase, stubs.FileWriter_Mixin):
    def setUp(self):
        logging.basicConfig(level=logging.DEBUG)
        self.db = stubs.testDB()
        self.cfg = stubs.testConfig()
        self.osmapi = osm.test.stubs.testOsmApi(datapath=cwd+'../osm/test/data')
        self.args = Args()
        self.requests = osm.test.stubs.testRequests(datapath=cwd+'../osm/test/data')
        self.dapi = osmdiff.OsmDiffApi()
        self.dapi.api = 'stub'
        self.amqp = mock.MagicMock()
        
class TestCsetDiff(BaseTest):

    @patch('osm.diff.requests.get')
    @patch('osm.poly.Poly')
    @patch('osm.changeset.OsmApi')
    def test_cset_diff_parse(self, OsmApi, Poly, UrlGet):
        OsmApi.return_value = self.osmapi
        Poly.return_value.contains_chgset.return_value = True
        UrlGet.side_effect = self.requests.get

        seqno = 1234
        head = self.dapi.get_state('changesets', seqno)

        csets = osmtracker.diff_fetch_single(self.args, self.cfg, self.dapi, self.db, self.amqp, seqno)
        self.assertEqual(len(csets), 1)
        self.assertTrue(23456 in csets.keys())
