
import unittest
import mock
from mock import patch
import logging
import osmtracker
import config
import sys
import os
import signal
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
    STATE_ANALYSING1 = 'ANALYSING1'         # Initial processing (meta etc)
    STATE_OPEN = 'OPEN'                     # Wait state
    STATE_CLOSED = 'CLOSED'                 # Staging state for deep analysis
    STATE_ANALYSING2 = 'ANALYSING2'         # Deeper analysis of closed csets
    STATE_REANALYSING = 'REANALYSING'       # Updates (notes etc)
    STATE_DONE = 'DONE'                     # For now, all analysis completed
    STATE_QUARANTINED = 'QUARANTINED'       # Temporary error experienced

    def __init__(self, admin=False, sigint_on=[]):
        self.sigint_on = sigint_on
        self.csets = []
        self.url = 'TESTDATABASE'
        self.generation = 1
        self.all_states = [self.STATE_NEW, self.STATE_BOUNDS_CHECK, self.STATE_BOUNDS_CHECKED,
                           self.STATE_ANALYSING1, self.STATE_OPEN,self. STATE_CLOSED,
                           self.STATE_ANALYSING2, self.STATE_REANALYSING,
                           self.STATE_DONE, self.STATE_QUARANTINED]
        self.pointer = {'stype': 'minute',
                        'seqno': 12345678,
                        'timestamp': datetime.datetime(2007, 7, 17, 10, 0, 0).replace(tzinfo=pytz.utc),
                        'first_pointer': {'stype': 'minute',
                                          'seqno': 12345670,
                                          'timestamp': datetime.datetime(2007, 7, 17, 8, 0, 0).replace(tzinfo=pytz.utc) }}

    def test_add_cid(self, cid, state=STATE_NEW, append=True):
        cset = {'cid' : cid, 'state': state, 'labels': [],
                'refreshed': datetime.datetime(2007, 7, 17, 0, 3, 4).replace(tzinfo=pytz.utc),
                'updated': datetime.datetime(2007, 7, 17, 0, 3, 4).replace(tzinfo=pytz.utc),
                'state_changed': datetime.datetime(2007, 7, 17, 0, 3, 4).replace(tzinfo=pytz.utc),
                'queued': datetime.datetime(2007, 7, 17, 0, 3, 4).replace(tzinfo=pytz.utc),
                'source': {'sequenceno': 123456,
                           'observed':datetime.datetime(2007, 7, 17, 8, 3, 4).replace(tzinfo=pytz.utc)}}
        if not append:
            self.csets = []
        self.csets.append(cset)
        return cset

    def pointer_meta_update(self, upd):
        for k,v in upd.iteritems():
            self.pointer[k] = v

    def pointer(self):
        return self.pointer

    def pointer_advance(self, offset=1):
        old = self.pointer['seqno']
        self.pointer['seqno'] = old+offset

    def generation_advance(self, offset=1):
        self.generation += offset

    def chgsets_count(self):
        return len(self.csets)
    
    def chgsets_find_selector(self, state=STATE_DONE, before=None, after=None, timestamp='updated', cid=None):
        sel = dict()
        if cid:
            sel['cid'] = cid
        if state:
            if type(state) is list:
                sel['state'] = {'$in': state}
            else:
                sel['state'] = state
        if before or after:
            sel[timestamp] = {}
        if before:
            sel[timestamp]['$lt'] = before
        if after:
            sel[timestamp]['$gte'] = after
            # Work-around for year entries in the future
            # See https://jira.mongodb.org/browse/PYTHON-557
            sel[timestamp]['$lte'] = datetime.datetime.max
        return sel

    def chgset_get(self, cid):
        for c in self.csets:
            if cid==c['cid']:
                return c
        return None
        
    def chgsets_find(self, state=STATE_DONE, before=None, after=None, timestamp='updated', sort=True, cid=None):
        found = []
        for c in self.csets:
            if cid and cid!=c['cid']:
                continue
            if type(state) is list:
                if c['state'] in state:
                    found.append(c)
            else:
                if c['state']==state or not state:
                    found.append(c)
        return DBcursor(found)

    def chgset_append(self, cid, source=None):
        return self.test_add_cid(cid)

    def chgset_start_processing(self, istate, nstate, before=None, after=None, timestamp='state_changed', cid=None):
        c = self.chgsets_find(istate, before, after, timestamp, cid=cid)
        if c:
            c = c[0]
            c['state'] = nstate
            return c
        return None

    def chgset_drop(self, cid):
        c = self.find_cset(cid)
        self.csets.remove(c)

    def chgset_processed(self, c, state, failed=False, refreshed=False):
        if 'chgset_processed' in self.sigint_on:
            os.kill(os.getpid(), signal.SIGINT)
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
        if 'chgset_get_meta' in self.sigint_on:
            os.kill(os.getpid(), signal.SIGINT)
        c = self.find_cset(cid)
        if not c or not 'meta' in c:
            return None
        return loads(c['meta'])

    def chgset_set_info(self, cid, info):
        c = self.find_cset(cid)
        c['info'] = dumps(info)

    def chgset_get_info(self, cid):
        c = self.find_cset(cid)
        if not c or not 'info' in c:
            if not c:
                logger.warn('Cset {} not found'.format(cid))
            else:
                logger.warn('Cset {} has no info, keys: {}'.format(cid, c.keys()))
            return None
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
	            {"area_file": "region.poly", "area_check_type": "cset-bbox", "label": "inside-area"},
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
	            "path": "dynamic",
	            "title": "Recent Changesets",
	            "filename" : "today.html",
	            "template": "changeset.html"
	        },
                {
                    "type": "BackendHtml",
                    "path": "dynamic",
                    "filename" : "notes.html",
                    "template": "notes.html"
                },
                {
                    "type": "BackendHtml",
                    "path": "dynamic",
	            "labels": ["address-node-change"],
	            "title": "Recent Changesets Which Modifies Address Nodes",
                    "filename" : "dk_addresses.html",
                    "template": "changeset.html"
                },
                {
                    "type": "BackendHtmlSummary",
                    "path": "dynamic",
                    "filename" : "today-summ.html",
                    "template": "summary.html"
                },
                {
                    "type": "BackendGeoJson",
                    "path": "dynamic",
	            "exptype": "cset-bbox",
                    "filename" : "today.json",
                    "click_url": "http://osm.expandable.dk/diffmap.html?cid={cid}"
                },
                {
                    "type": "BackendGeoJson",
                    "path": "dynamic",
	            "exptype": "cset-files",
	            "geojsondiff-filename": "cset-{id}.json",
	            "bounds-filename": "cset-{id}.bounds",
                    "click_url": "http://osm.expandable.dk/diffmap.html?cid={cid}"
                },
                {
                    "type": "BackendHtml",
	            "init_only": True,
                    "map_center": "56.0, 11.4",
                    "map_scale": "6",
                    "path": "",
                    "filename" : "index.html",
                    "template": "index.html"
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
