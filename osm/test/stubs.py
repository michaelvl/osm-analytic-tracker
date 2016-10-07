
import unittest
import mock
from mock import patch
import logging
import sys
import datetime, pytz
import json

logger = logging.getLogger('')

class testOsmApi(object):
    def __init__(self, datapath='test/data'):
        self.datapath = datapath

    def _dateconv(self, txt):
        return datetime.datetime.strptime(txt, "%Y-%m-%dT%H:%M:%SZ")

    def keys2int(self, data):
        nw = {}
        for k in data.keys():
            nw[int(k)] = data[k]
        return nw

    def ChangesetGet(self, id, include_discussion=True):
        with open(self.datapath+'/cset{}.meta.json'.format(id)) as f:
            data =json.load(f)
        for ts in ['created_at', 'closed_at']:
            if ts in data:
                data[ts] = self._dateconv(data[ts])
        logger.debug(' Loaded changeset meta {}'.format(data))
        return data

    def ChangesetDownload(self, id):
        # Note that osmapi returns empty node list ('nd') and tag list ('tag')
        # for deleted ways. The OSM change file do not contain such an empty
        # list.
        with open(self.datapath+'/cset{}.data.json'.format(id)) as f:
            data = json.load(f)
        # FIXME: Notes timestamps
        for elem in data:
            edata = elem['data']
            if 'timestamp' in edata:
                edata['timestamp'] = self._dateconv(edata['timestamp'])
        logger.debug(' Loaded changeset data {}'.format(data))
        return data

    def NodeHistory(self, id):
        with open(self.datapath+'/node{}.data.json'.format(id)) as f:
            data = self.keys2int(json.load(f))
        for v in data.keys():
            data[v]['timestamp'] = self._dateconv(data[v]['timestamp'])
        return data

    def NodeGet(self, id, NodeVersion):
        data = self.NodeHistory(id)
        if NodeVersion in data:
            return data[NodeVersion]
        return None

    def WayGet(self, id, WayVersion):
        with open(self.datapath+'/way{}.data.json'.format(id)) as f:
            data = self.keys2int(json.load(f))
        if WayVersion in data:
            w = data[WayVersion]
            w['timestamp'] = self._dateconv(w['timestamp'])
            return w
        return None
