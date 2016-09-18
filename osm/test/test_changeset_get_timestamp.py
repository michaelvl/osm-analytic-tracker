#!/usr/bin/env python

import unittest
import mock
from mock import patch
import logging
import changeset
import diff
import stubs
import datetime, pytz

logger = logging.getLogger('')

class TestTimestamps(unittest.TestCase):

    def setUp(self):
        #logging.basicConfig(level=logging.DEBUG)
        self.cset = changeset.Changeset(id=10)
        self.osmapi = stubs.testOsmApi()

    def test_get_timestamp(self):
        self.cset.meta = {'user': 'useruser', 'tag': {'comment': 'Adjustments at somewhere'},
                          "open": False,
                          "created_at": datetime.datetime(2015,5,1,16,9,37).replace(tzinfo=pytz.utc),
                          "closed_at":  datetime.datetime(2015,5,1,16,10,37).replace(tzinfo=pytz.utc),
                          "comments_count": 3,
                          "discussion": [
                              {"date": datetime.datetime(2015,5,1,16,11,37).replace(tzinfo=pytz.utc),
                               "text": "Comment 1"},
                              {"date": datetime.datetime(2015,5,1,16,12,37).replace(tzinfo=pytz.utc),
                               "text": "Comment 2"},
                              {"date": datetime.datetime(2015,5,1,16,13,37).replace(tzinfo=pytz.utc),
                               "text": "Comment 3"}
                          ]}
        ts = self.cset.get_timestamp(self.cset.meta)[1]
        self.assertEqual(ts, self.cset.meta['closed_at'])
        ts = self.cset.get_timestamp(self.cset.meta, include_discussion=True)[1]
        self.assertEqual(ts, self.cset.meta['discussion'][2]['date'])

if __name__ == '__main__':
    unittest.main()
