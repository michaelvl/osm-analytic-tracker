#!/usr/bin/python

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


if __name__ == '__main__':
    unittest.main()
