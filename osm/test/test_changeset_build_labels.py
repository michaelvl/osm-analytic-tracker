#!/usr/bin/env python

import unittest
import mock
from mock import patch
import logging
import changeset
import stubs

logger = logging.getLogger('')

class TestLabelFilter(unittest.TestCase):

    def setUp(self):
        #logging.basicConfig(level=logging.DEBUG)
        self.cset = changeset.Changeset(id=10)
        self.osmapi = stubs.testOsmApi()

    @patch('poly.Poly')
    def test_1(self, Poly):
        self.cset.meta = {'user': 'useruser', 'tag': {'comment': 'Adjustments at somewhere'}}
        labels = [
	    {"area": "region.poly", "label": "inside-area"},
	    {"regex": [{".meta.tag.comment": "^Adjustments"}], "label": "adjustment"}
	]
        Poly.return_value.contains_chgset.return_value = True
        labels = self.cset.build_labels(labels)
        self.assertTrue('adjustment' in labels)
        self.assertTrue('inside-area' in labels)

    @patch('poly.Poly')
    #@patch('changeset.OsmApi')
    def test_1_cset_data_labels(self, Poly):
        self.cset.meta = {'user': 'useruser', 'tag': {'comment': 'Adjustments at somewhere'}}
        self.cset.changes = [{"action": "modify",
                              "data": {"changeset": 10,
                                       "id": 10000,
                                       "lat": 54.0,
                                       "lon": 10.0,
                                       "tag": {"some-tag-identifier": "123456789"},
                                       "timestamp":  "2016-05-01T16:19:37Z",
                                       "uid": 1000,
                                       "user": "Karl Koder",
                                       "version": 1,
                                       "visible": True},
                              "type": "node"}]
        labels = [
	    {"regex": [{".meta.tag.comment": "^Adjustments",
                        ".changes.modify.node.tag.some-tag-identifier": ""}], "label": "a-change"}
	]
        #OsmApi.return_value = self.osmapi
        Poly.return_value.contains_chgset.return_value = True
        labels = self.cset.build_labels(labels)
        self.assertTrue('a-change' in labels)

        labels = [
	    {"regex": [{".meta.tag.comment": "^Adjustments",
                        ".changes.modify.tag.some-tag-identifier": ""}], "label": "a-change"}
	]
        labels = self.cset.build_labels(labels)
        self.assertTrue('a-change' in labels)

        labels = [
	    {"regex": [{".meta.tag.comment": "^Adjustments",
                        ".changes.delete.tag.some-tag-identifier": ""}], "label": "a-change"}
	]
        labels = self.cset.build_labels(labels)
        self.assertFalse('a-change' in labels)

        labels = [
	    {"regex": [{".meta.tag.comment": "^Adjustments",
                        ".changes.node.tag.some-tag-identifier": ""}], "label": "a-change"}
	]
        labels = self.cset.build_labels(labels)
        self.assertTrue('a-change' in labels)

        labels = [
	    {"regex": [{".meta.tag.comment": "^Adjustments",
                        ".changes.tag.some-tag-identifier": ""}], "label": "a-change"}
	]
        labels = self.cset.build_labels(labels)
        self.assertTrue('a-change' in labels)

        labels = [
	    {"regex": [{".meta.tag.comment": "^Adjustments",
                        ".changes.way.tag.some-tag-identifier": ""}], "label": "a-change"}
	]
        labels = self.cset.build_labels(labels)
        self.assertFalse('a-change' in labels)

    @patch('poly.Poly')
    def test_1_area_fail(self, Poly):
        labels = [
	    {"area": "region.poly", "label": "inside-area"},
	]
        Poly.return_value.contains_chgset.return_value = False
        labels = self.cset.build_labels(labels)
        self.assertFalse('inside-area' in labels)


if __name__ == '__main__':
    unittest.main()
