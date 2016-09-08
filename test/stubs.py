
import unittest
import mock
from mock import patch
import logging
import osmtracker
import config
import sys
import datetime, pytz
import json

logger = logging.getLogger('')

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

    def __init__(self):
        self.csets = [{'cid' : 10, 'state': self.STATE_NEW, 'labels': [],
                       'source': {'sequenceno': 123456,
                                  'observed':datetime.datetime(2007, 7, 17, 8, 3, 4).replace(tzinfo=pytz.utc)}}]
        self.url = 'TESTDATABASE'
        self.generation = 1
        self.pointer = {'stype': 'minute',
                        'seqno': 12345678,
                        'timestamp': datetime.datetime(2007, 7, 17, 10, 0, 0).replace(tzinfo=pytz.utc),
                        'first_pointer': {'stype': 'minute',
                                          'seqno': 12345670,
                                          'timestamp': datetime.datetime(2007, 7, 17, 8, 0, 0).replace(tzinfo=pytz.utc) }}

    def chgsets_count(self):
        return len(self.csets)
    
    def chgsets_find(self, state=STATE_DONE, before=None, after=None, timestamp='updated', sort=True):
        for c in self.csets:
            if type(state) is list:
                if c['state'] in state:
                    return [c]
            else:
                if c['state']==state:
                    return [c]
        return []

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
        
    def chgset_set_meta(self, cid, meta):
        c = self.find_cset(cid)
        c['meta'] = meta

    def chgset_get_meta(self, cid):
        c = self.find_cset(cid)
        return c['meta']

    def chgset_set_info(self, cid, info):
        c = self.find_cset(cid)
        c['info'] = info

    def chgset_get_info(self, cid):
        c = self.find_cset(cid)
        return c['info']

        
class testConfig(config.Config):
    def __init__(self):
        self.cfg = {
            "path": "html",
            "tracker": {
	        "osm_api_url": "https://api.openstreetmap.org",
	        "geojsondiff-filename": "cset-{id}.json",
	        "bounds-filename": "cset-{id}.bounds",
	        "pre_labels": [
	            {"area": "region.poly", "area_check_type": "bbox", "label": "inside-area"},
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
                    "filename" : "today.json",
                    "click_url": "http://osm.expandable.dk/diffmap.html?cid={cid}"
                }
            ]
        }

    def load(self, what, who=None, default=None):
        pass
