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

class Args:
    def __init__(self):
        self.metrics = True
        self.track = False

class BaseTest(unittest.TestCase, stubs.FileWriter_Mixin):
    def setUp(self):
        #logging.basicConfig(level=logging.DEBUG)
        self.db = stubs.testDB()
        self.cfg = stubs.testConfig()
        self.osmapi = osm.test.stubs.testOsmApi(datapath='osm/test/data')
        self.filewritersetup()
        self.listdir = ['today.html', 'cset-10.json', 'cset-10.bounds', 'cset-3.json', 'cset-3.bounds']
        self.args = Args()
        
class TestCsetFilter(BaseTest):

    @patch('db.do_reanalyze')
    def test_supervisor(self, DbRea):
        self.db.test_add_cid(10, append=False, state=self.db.STATE_NEW)

        osmtracker.supervisor(None, self.cfg, self.db)
        osmtracker.supervisor(self.args, self.cfg, self.db)
        #print 'xx', Db.mock_calls
        DbRea.assert_has_calls([call(mock.ANY, mock.ANY, mock.ANY, 'NEW')])


if __name__ == '__main__':
    unittest.main()
