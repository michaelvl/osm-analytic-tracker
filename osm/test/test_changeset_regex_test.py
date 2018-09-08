#!/usr/bin/env python

import unittest
import logging
import changeset

logger = logging.getLogger('')

class TestFiltering(unittest.TestCase):

    def setUp(self):
        #logging.basicConfig(level=logging.DEBUG)
        self.cset = changeset.Changeset(id=1)

    def test_1_non_ext_key(self):
        self.cset.meta = {'user': 'useruser', 'tag': {'comment': 'Adjustments at somewhere'}}
        regexfilter = [{".meta.tag.xxcomment": "^Adjustments"}]
        self.assertFalse(self.cset.regex_test(regexfilter))

    def test_1_non_ext_key2(self):
        self.cset.meta = {'user': 'useruser', 'tag': {'comment': 'Adjustments at somewhere'}}
        regexfilter = [{"...meta.tag.xxcomment": "^Adjustments"}]
        self.assertFalse(self.cset.regex_test(regexfilter))

    def test_1_non_ext_key3(self):
        self.cset.meta = {'user': 'useruser', 'tag': {'comment': 'Adjustments at somewhere'}}
        regexfilter = [{"...": "^Adjustments"}]
        self.assertFalse(self.cset.regex_test(regexfilter))

    def test_1_match(self):
        self.cset.meta = {'user': 'useruser', 'tag': {'comment': 'Adjustments at somewhere'}}
        regexfilter = [{".meta.tag.comment": "^Adjustments"}]
        self.assertTrue(self.cset.regex_test(regexfilter))

    #def test_1_match_case_insensitive(self):
    #    self.cset.meta = {'user': 'useruser', 'tag': {'comment': 'Adjustments at somewhere'}}
    #    regexfilter = [{".meta.tag.comment": "adjustments"}]
    #    self.assertTrue(self.cset.regex_test(regexfilter))

    def test_1_match2(self):
        self.cset.meta = {'user': 'useruser', 'tag': {'comment': 'Adjustments at somewhere 123'}}
        regexfilter = [{".meta.tag.comment": "^Adjustments at somewhere \d+"}]
        self.assertTrue(self.cset.regex_test(regexfilter))

    def test_1_match3(self):
        self.cset.meta = {'user': 'useruser', 'tag': {'comment': 'Adjustments at somewhere #fixfix'}}
        regexfilter = [{".meta.tag.comment": ".*#fixfix"}]
        self.assertTrue(self.cset.regex_test(regexfilter))

    def test_2_match(self):
        self.cset.meta = {'user': 'useruser', 'tag': {'comment': 'Adjustments at somewhere'}}
        regexfilter = [{".meta.tag.comment": "^Adjustments", '.meta.user': 'useruser'}]
        self.assertTrue(self.cset.regex_test(regexfilter))

    def test_1_nonmatch(self):
        self.cset.meta = {'user': 'useruser', 'tag': {'comment': 'Adjustment of fooBar'}}
        regexfilter = [{".meta.tag.comment": "^Adjustments"}]
        self.assertFalse(self.cset.regex_test(regexfilter))

    def test_2_nonmatch(self):
        self.cset.meta = {'user': 'useruser', 'tag': {'comment': 'Adjustments at somewhere'}}
        regexfilter = [{".meta.tag.comment": "^Adjustments", '.meta.user': 'anotheruser'}]
        self.assertFalse(self.cset.regex_test(regexfilter))


    # See also test_1_cset_data_labels in test_changeset_build_labels.py
    def test_changes(self):
        self.cset.changes = [{"action": "delete",
                              "data": {"changeset": 1212,
                                       "id": 10102,
                                       "timestamp": "2016-05-01T16:19:37Z",
                                       "uid": 2345678,
                                       "user": "Deleter",
                                       "version": 2,
                                       "visible": False},
                              "type": "node"}
        ]
        self.cset.hist = {"node": {
            10102: {
                1: {"changeset": 10,
                    "id": 10102,
                    "lat": 54.1,
                    "lon": 10.1,
                    "tag": {"osak:identifier": "1234"},
                    "timestamp": "2015-05-01T16:19:37Z",
                    "uid": 2345678,
                    "user": "Ronny the Rover",
                    "version": 1,
	            "visible": True},
                2: {"changeset": 12,
                    "id": 10102,
                    "tag": {},
                    "timestamp": "2016-05-01T16:19:37Z",
                    "uid": 2345679,
                    "user": "Cleaner bot",
                    "version": 2,
	            "visible": False}
            }
        }}
        regexfilter = [{".changes.tag.osak:identifier": ""}]
        self.assertTrue(self.cset.regex_test(regexfilter))


if __name__ == '__main__':
    unittest.main()
