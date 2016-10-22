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
        logging.basicConfig(level=logging.DEBUG)
        self.db = stubs.testDB()
        self.db.test_add_cid(10)
        self.cfg = stubs.testConfig()
        self.osmapi = osm.test.stubs.testOsmApi(datapath='osm/test/data')
        self.filewritersetup()
        self.listdir = ['today.html', 'cset-10.json', 'cset-10.bounds', 'cset-3.json', 'cset-3.bounds']
        
class TestCsetFilter(BaseTest):

    @patch('osmtracker.BackendGeoJson.remove')
    @patch('osmtracker.BackendGeoJson.listdir')
    @patch('osmtracker.BackendGeoJson.isfile')
    @patch('tempfilewriter.TempFileWriter')
    @patch('osm.poly.Poly')
    @patch('osm.changeset.OsmApi')
    def xtest_cset_filter1_and_backend(self, OsmApi, Poly, FileWriter, IsFile, Listdir, Remove):
        IsFile.return_value = True
        Listdir.return_value = self.listdir
        OsmApi.return_value = self.osmapi
        Poly.return_value.contains_chgset.return_value = True
        FileWriter.side_effect = self.fstart
        osmtracker.csets_filter(None, self.cfg, self.db)
        self.assertEqual(self.db.csets[0]['state'], self.db.STATE_BOUNDS_CHECKED)

        osmtracker.csets_analyze_initial(None, self.cfg, self.db)
        osmtracker.csets_analyze_on_close(None, self.cfg, self.db)

        #print 'DB:{}'.format(pprint.pformat(self.db.csets))

        self.cfg.cfg['backends'][0]['labels'] = ['adjustments']
        osmtracker.run_backends(None, self.cfg, self.db)
        #print 'files:', self.files.keys()
        #print 'xx', FileWriter.mock_calls
        #self.print_file('html/today.html')
        #self.print_file('html/dk_addresses.html')
        #self.print_file('html/today-summ.html')
        #print 'filemocks', self.filemocks[0].mock_calls
        self.assertTrue('No changesets' not in self.files['html/today.html'])
        self.assertTrue('-- Changeset 10 source' in self.files['html/today.html'])
        self.assertTrue('Total navigable: 12,888 meters (6,444m/hour)' in self.files['html/today-summ.html'])
        self.assertTrue('1 changesets by 1 user' in self.files['html/today-summ.html'])

        #print 'Remove mock calls', Remove.mock_calls
        Remove.assert_has_calls([call('html/cset-3.json'), call('html/cset-3.bounds')])
        self.assertEqual(len(Remove.mock_calls), 2)
        
        # Rerun with non-matching labels
        self.cfg.cfg['backends'][0]['labels'] = ['xxadjustments']
        osmtracker.run_backends(None, self.cfg, self.db)
        #self.print_file('html/today.html')
        self.assertTrue('No changesets' in self.files['html/today.html'])

        self.assertTrue('html/cset-10.json' in self.files)
        #self.print_file('html/cset-10.json')
        self.assertTrue('FeatureCollection' in self.files['html/cset-10.json'])
        self.assertTrue('html/cset-10.bounds' in self.files)
        #self.print_file('html/cset-10.bounds')
        self.assertTrue('5,7,10,14' in self.files['html/cset-10.bounds'])

    @patch('osm.poly.Poly')
    @patch('osm.changeset.OsmApi')
    def xtest_cset_filter2(self, OsmApi, Poly):
        '''Cset has single label, filter list have two elements, test that cset is
           dropped since it does not have both from filter list
        '''
        OsmApi.return_value = self.osmapi
        Poly.return_value.contains_chgset.return_value = False
        osmtracker.csets_filter(None, self.cfg, self.db)
        self.assertTrue(len(self.db.csets)==0) # Filtered out since list is logical AND

    @patch('osm.poly.Poly')
    @patch('osm.changeset.OsmApi')
    def xtest_cset_filter3(self, OsmApi, Poly):
        '''Cset has single label, filter list have single element, test that cset is
           kept.
        '''
        OsmApi.return_value = self.osmapi
        Poly.return_value.contains_chgset.return_value = False
        self.cfg.cfg['tracker']['prefilter_labels'] = [["adjustments"]]
        osmtracker.csets_filter(None, self.cfg, self.db)
        self.assertTrue(len(self.db.csets)==1)

    @patch('osm.poly.Poly')
    @patch('osm.changeset.OsmApi')
    def test_cset_filter4(self, OsmApi, Poly):
        '''Cset has single label, filter list have single elements, test that cset is
           kept.
        '''
        OsmApi.return_value = self.osmapi
        Poly.return_value.contains_chgset.return_value = False
        self.cfg.cfg['tracker']['prefilter_labels'] = [["adjustmentsxx"], ['mapping-event']]
        self.cfg.cfg['tracker']['pre_labels'].append({"regex": [{".meta.tag.comment": ".*#\\w+"}], "label": "mapping-event"})
        osmtracker.csets_filter(None, self.cfg, self.db)
        self.assertTrue(len(self.db.csets)==1)

# class TestCsetFilter(BaseTest):

#     #@patch('config.Config')
#     #@patch('db.DataBase')
#     @patch('osm.changeset')
#     def test_1(self, Cset, Db, Config):
#         self.db.csets = [{'cid' : 10, 'state': db.DataBase.STATE_NEW}]
#         #Db.return_value = self.db
#         #Config.return_value.get = self.cfgget
#         #args = ['osmtracker', 'csets-filter']
#         #with patch.object(sys, 'argv', args):
#         #    osmtracker.main()
#         osmtracker.csets_filter(None, self.cfg, self.db, None)
#         self.assertEqual(self.db.csets[0]['state'], db.DataBase.STATE_BOUNDS_CHECKED)

if __name__ == '__main__':
    unittest.main()
