#!/usr/bin/env python

import unittest
import mock
from mock import patch
import logging
import changeset
import stubs
import pprint

logger = logging.getLogger('')

class TestImportExportAndGeojson(unittest.TestCase):

    def setUp(self):
        #logging.basicConfig(level=logging.DEBUG)
        self.osmapi = stubs.testOsmApi()

    @patch('poly.Poly')
    @patch('changeset.OsmApi')
    def test_1_export_import_and_geojson(self, OsmApi, Poly):
        OsmApi.return_value = self.osmapi
        Poly.return_value.contains_chgset.return_value = True
        self.cset = changeset.Changeset(id=10)
        self.cset.downloadMeta()
        self.cset.downloadData()
        self.cset.downloadGeometry()

        data = self.cset.data_export()

        #print 'data[changes]: {}'.format(pprint.pformat(data['changes']))
        #print 'data[geometry]: {}'.format(pprint.pformat(data['geometry']))
        #print 'xx', OsmApi.mock_calls

        cset = changeset.Changeset(id=10, api=None)
        data = cset.data_import(data)
        geoj = cset.getGeoJsonDiff()
        self.assertTrue('features' in geoj)
        self.assertTrue(len(geoj['features'])>0)
        #print 'GEOJ:{}'.format(pprint.pformat(geoj))

if __name__ == '__main__':
    unittest.main()
