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
        self.cset.meta = {}
        self.osmapi = stubs.testOsmApi()

    @patch('poly.Poly')
    def test_1(self, Poly):
        self.cset.meta = {'user': 'useruser', 'tag': {'comment': 'Adjustments at somewhere'}}
        labels = [
	    {"area_file": "region.poly", "label": "inside-area"},
	    {"regex": [{".meta.tag.comment": "^Adjustments"}], "label": "adjustment"}
	]
        Poly.return_value.contains_chgset.return_value = True
        labels = self.cset.build_labels(labels)
        self.assertTrue('adjustment' in labels)
        self.assertTrue('inside-area' in labels)

    @patch('poly.Poly')
    def test_1_bbox_center(self, Poly):
        self.cset.meta = {'user': 'useruser', 'tag': {'comment': 'Adjustments at somewhere'},
                          'min_lat': '48.00', 'max_lat': '50.00', 'min_lon': '50.00', 'max_lon': '52.00'}
        labels = [
	    {"area_file": "region.poly", "area_check_type": "cset-center", "label": "cset-center-inside-area"},
	]
        Poly.return_value.contains_chgset.return_value = True
        labels = self.cset.build_labels(labels)
        self.assertTrue('cset-center-inside-area' in labels)
        #print 'polymocks', Poly.mock_calls
        Poly.return_value.contains.assert_called_once_with(51.0, 49.0)

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
                                       "version": 2,
                                       "visible": True},
                              "type": "node"}]
        self.cset.hist = {"node": {
            10000: {
                1: {"changeset": 9,
                    "id": 10000,
                    "lat": 54.1,
                    "lon": 10.1,
                    "tag": {"osak:identifier": "1234"},
                    "timestamp": "2015-05-01T16:19:37Z",
                    "uid": 2345678,
                    "user": "Ronny the Rover",
                    "version": 1,
	            "visible": True}
            }
        }}
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
	    {"area_file": "region.poly", "label": "inside-area"},
	]
        Poly.return_value.contains_chgset.return_value = False
        labels = self.cset.build_labels(labels)
        self.assertFalse('inside-area' in labels)


if __name__ == '__main__':
    unittest.main()
