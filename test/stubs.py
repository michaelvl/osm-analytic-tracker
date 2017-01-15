
import unittest
import mock
from mock import patch
import logging
import osmtracker
import config
import sys
import datetime, pytz
from bson.json_util import dumps, loads

logger = logging.getLogger('')

class DBcursor(object):
    def __init__(self, clist):
        self.clist = clist

    def __iter__(self):
        self.idx = 0
        return self

    def next(self):
        return self.__next__()
    def __next__(self):
        if self.idx >= len(self.clist):
            raise StopIteration
        val = self.clist[self.idx]
        self.idx += 1
        return val

    def __getitem__(self, key):
        if len(self.clist)==0:
            return None
        return self.clist[key]

    def __nonzero__(self):
        return len(self.clist)!=0
    def __bool__(self):
        return len(self.clist)!=0

    def explain(self):
        return dict()

class testDB(object):
    STATE_NEW = 'NEW'
    STATE_BOUNDS_CHECK = 'BOUNDS_CHECK'     # Used for combined bounds and regex filtering
    STATE_BOUNDS_CHECKED = 'BOUNDS_CHECKED' # Cset passed filter
    STATE_ANALYZING1 = 'ANALYZING1'         # Initial processing (meta etc)
    STATE_OPEN = 'OPEN'                     # Wait state
    STATE_CLOSED = 'CLOSED'                 # Staging state for deep analysis
    STATE_ANALYZING2 = 'ANALYZING2'         # Deeper analysis of closed csets
    STATE_REANALYZING = 'REANALYZING'       # Updates (notes etc)
    STATE_DONE = 'DONE'                     # For now, all analysis completed

    def __init__(self, admin=False):
        self.csets = []
        self.test_add_cid(10)
        self.url = 'TESTDATABASE'
        self.generation = 1
        self.pointer = {'stype': 'minute',
                        'seqno': 12345678,
                        'timestamp': datetime.datetime(2007, 7, 17, 10, 0, 0).replace(tzinfo=pytz.utc),
                        'first_pointer': {'stype': 'minute',
                                          'seqno': 12345670,
                                          'timestamp': datetime.datetime(2007, 7, 17, 8, 0, 0).replace(tzinfo=pytz.utc) }}

    def test_add_cid(self, cid):
        self.csets = [{'cid' : cid, 'state': self.STATE_NEW, 'labels': [],
                       'refreshed': datetime.datetime(2007, 7, 17, 0, 3, 4).replace(tzinfo=pytz.utc),
                       'source': {'sequenceno': 123456,
                                  'observed':datetime.datetime(2007, 7, 17, 8, 3, 4).replace(tzinfo=pytz.utc)}}]

    def chgsets_count(self):
        return len(self.csets)
    
    def chgsets_find(self, state=STATE_DONE, before=None, after=None, timestamp='updated', sort=True):
        found = []
        for c in self.csets:
            if type(state) is list:
                if c['state'] in state:
                    found.append(c)
            else:
                if c['state']==state:
                    found.append(c)
        return DBcursor(found)

    def chgset_start_processing(self, istate, nstate, before=None, after=None, timestamp='state_changed'):
        c = self.chgsets_find(istate, before, after, timestamp)
        if c:
            c = c[0]
            c['state'] = nstate
            return c
        return None

    def chgset_drop(self, cid):
        c = self.find_cset(cid)
        self.csets.remove(c)

    def chgset_processed(self, c, state, failed=False, refreshed=False):
        c['state'] = state

    def find_cset(self, cid):
        for c in self.csets:
            if c['cid']==cid:
                return c

    # Loads and dumps below are to simulate int->string dict-key conversion
    def chgset_set_meta(self, cid, meta):
        c = self.find_cset(cid)
        c['meta'] = dumps(meta)

    def chgset_get_meta(self, cid):
        c = self.find_cset(cid)
        return loads(c['meta'])

    def chgset_set_info(self, cid, info):
        c = self.find_cset(cid)
        c['info'] = dumps(info)

    def chgset_get_info(self, cid):
        c = self.find_cset(cid)
        return loads(c['info'])

    def show_brief(self, args, db, reltime=True):
        pass

        
class testConfig(config.Config):
    def __init__(self):
        self.cfg = {
            "path": "html",
            "tracker": {
	        "osm_api_url": "https://api.openstreetmap.org",
	        "geojsondiff-filename": "cset-{id}.json",
	        "bounds-filename": "cset-{id}.bounds",
	        "pre_labels": [
	            {"area": "region.poly", "area_check_type": "cset-bbox", "label": "inside-area"},
	            {"regex": [{".meta.tag.comment": "^Adjustments"}], "label": "adjustments"}
	        ],
	        "prefilter_labels": [["inside-area", "adjustments"]],
	        "post_labels": [
	            {"regex": [{".changes.tag.osak:identifier": ""}], "label": "address-node-change"}
	        ],
	        "history": "5 minutes ago",
	        "horizon_type": "sliding",
	        "horizon_hours": 48,
	        "refresh_open_minutes": 5,
	        "refresh_meta_minutes": 15,
	        "cset_processing_time_max_s": 300,
	        "template_path": "templates"
            },
            "backends": [
	        {
	            "type": "BackendHtml",
	            "show_details": True,
	            "show_comments": True,
	            "path": "",
	            "title": "Recent Changesets",
	            "filename" : "today.html",
	            "template": "changeset.html"
	        },
                {
                    "type": "BackendHtml",
                    "path": "",
                    "filename" : "notes.html",
                    "template": "notes.html"
                },
                {
                    "type": "BackendHtml",
                    "path": "",
	            "labels": ["address-node-change"],
	            "title": "Recent Changesets Which Modifies Address Nodes",
                    "filename" : "dk_addresses.html",
                    "template": "changeset.html"
                },
                {
                    "type": "BackendHtmlSummary",
                    "filename" : "today-summ.html",
                    "template": "summary.html"
                },
                {
                    "type": "BackendGeoJson",
                    "path": "",
	            "exptype": "cset-bbox",
                    "filename" : "today.json",
                    "click_url": "http://osm.expandable.dk/diffmap.html?cid={cid}"
                },
                {
                    "type": "BackendGeoJson",
                    "path": "",
	            "exptype": "cset-files",
	            "geojsondiff-filename": "cset-{id}.json",
	            "bounds-filename": "cset-{id}.bounds",
                    "click_url": "http://osm.expandable.dk/diffmap.html?cid={cid}"
                }
            ]
        }

    def load(self, what, who=None, default=None):
        pass


class FileWriter_Mixin():
    def filewritersetup(self):
        self.files = {}
        self.filemocks = []
        self.curfile = None

    def fstart(self, fname):
        self.curfile = fname
        self.files[self.curfile] = ''
        mm = mock.MagicMock()
        mm.__enter__.return_value.write.side_effect = self.fwrite
        self.filemocks.append(mm)
        return mm

    def fwrite(self, txt):
        #print 'zz fwrite', txt
        self.files[self.curfile] += txt

    def print_file(self, fname):
        ff = self.files[fname].split('\n')
        print '|----- {} -------------------'.format(fname)
        for ln in ff:
            print '|', ln
        print '|--------------------------------'
