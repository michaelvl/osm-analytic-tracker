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

class Args:
    def __init__(self):
        self.metrics = True
        self.track = False
        self.amqp_url = 'AMQPURL'

class BaseTest(unittest.TestCase, stubs.FileWriter_Mixin):
    def setUp(self):
        #logging.basicConfig(level=logging.DEBUG)
        self.db = stubs.testDB()
        self.cfg = stubs.testConfig()
        self.osmapi = osm.test.stubs.testOsmApi(datapath=cwd+'../osm/test/data')
        self.filewritersetup()
        self.listdir = ['today.html', 'cset-10.json', 'cset-10.bounds', 'cset-3.json', 'cset-3.bounds']
        self.args = Args()
        
class TestCsetFilter(BaseTest):

    @patch('osmtracker.messagebus.Amqp')
    @patch('db.do_reanalyse')
    def test_supervisor(self, DbRea, MsgBus):
        self.db.test_add_cid(10, append=False, state=self.db.STATE_OPEN)
        self.db.csets[0]['refreshed'] = datetime.datetime(2007, 6, 17, 0, 3, 4).replace(tzinfo=pytz.utc)
        osmtracker.supervisor(self.args, self.cfg, self.db)
        #print 'Db calls', DbRea.mock_calls
        #DbRea.assert_has_calls([call(mock.ANY, mock.ANY, mock.ANY, 'NEW')])
        #print 'MsgBus calls', MsgBus.mock_calls
        MsgBus.assert_has_calls([call().send(mock.ANY, mock.ANY, mock.ANY, mock.ANY, mock.ANY)])

if __name__ == '__main__':
    unittest.main()
