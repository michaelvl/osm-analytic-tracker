import sys
import datetime, pytz
import urllib2
import gzip
from StringIO import StringIO
from osmapi import OsmApi
import xml.etree.ElementTree as etree
import logging

logger = logging.getLogger(__name__)

class OsmDiffException(Exception):
    pass

class OsmDiffApi(object):
    def __init__(self):
        #self.state_cache = {}
        #self.diff_cache = {}
        self.head_state = {}
        self.api = 'http://planet.osm.org'
        self.netstat = [0,0] # rx, tx bytes
        
        # Non-simple below
        #self.update_head_state()
        self.osmapi = OsmApi()

    def update_head_state(self, stype):
        state = self.get_state(stype, seqno=None)
        self.head_state[stype] = state
        logger.debug('Newest ' + str(self.head_state[stype]))

    def update_head_states(self):
        """ Update most recent states for daily, hourly and minutely"""
        logger.debug("Updating 'most recent' state")
        self.state = {}
        for stype in ('day', 'hour', 'minute'):
            self.update_head_state(stype)

    def get_state(self, stype, seqno=None):
        """ Get most recent state object of a given type (day, hour or minute) """
        #if seqno==None and self.head_state.has_key(stype):
        #    return self.head_state[stype]
        #if seqno and self.state_cache.has_key(stype+str(seqno)):
        #    logger.debug("Getting cached state '"+stype+"' sequenceNo "+str(seqno)+" from cache")
        #    return self.state_cache[stype+str(seqno)]
        state = State(stype=stype, autoload=False, seqno=seqno)
        logger.debug("### Retrieving '"+stype+"' state, seqno "+str(state.sequenceno()))
        state.load_state()
        #self.state_cache[stype+str(state.sequenceno())] = state
        logger.debug("Loaded state: "+str(state))
        return state

    def get_diff_from_state(self, state):
        return self.get_diff(state.sequenceno(), state.type)

    def get_diff(self, seqno, type):
        diff = Diff(seqno, type)
        diff.get(self.osmapi)
        return diff

    def get_diff_csets(self, seqno, type):
        diff = Diff(seqno, type)
        csets = diff.get_csets(self.osmapi)
        return csets

    def get_seqno_le_timestamp(self, type, timestamp, start, max_iter=None):
        """Get state object that has timestamp less than or equal to supplied
           timestamp. Searching back from supplied start object"""
        ptr = start
        seqno = ptr.sequenceno()
        if type=='minute':
            now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
            secs = (now-timestamp).total_seconds()
            if secs > 10:
                skip = int((now-timestamp).total_seconds()/60)
                seqno -= skip
                ptr = self.get_state(type, seqno)
                logger.debug('Skipping {} sequence numbers, now={}, search timestamp={}, new ptr timestamp={}'.format(skip, now, timestamp, ptr.timestamp()))
        if max_iter:
            iter = seqno-max_iter
        else:
            iter = seqno+1 # Infinite
        while ptr.timestamp() > timestamp and ptr.sequenceno() != iter and seqno > 0:
            seqno -= 1
            ptr = self.get_state(type, seqno)
        if ptr.timestamp() > timestamp:
            return None
        return ptr

    @staticmethod
    def timetxt2datetime(ts):
        if isinstance(ts, datetime.datetime):
            return ts
        return datetime.datetime.strptime(ts, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=pytz.utc)

class Base(object):
    repl_url = 'http://planet.osm.org/replication/'

    def __init__(self, type=None):
        self.state = {}
        if type == None:
            self.type = 'minute'
        else:
            self.type = type

    def _path_frag(self):
        seqno = self.sequenceno()
        a = seqno/1000000
        b = (seqno/1000)%1000
        c = seqno % 1000
        return '{:03d}/{:03d}/{:03d}'.format(a,b,c)

    def timestamp_str(self):
        return self.state['timestamp']

    def timestamp(self):
        return self.state['timestamp_dt']

    def sequenceno(self):
        if self.state.has_key('sequenceNumber'):
            return self.state['sequenceNumber']
        else:
            return None

    def set_sequenceno(self, seqno):
        self.state['sequenceNumber'] = seqno


class Diff(Base):
    """OSM diff class"""
    def __init__(self, seqno, type=None):
        Base.__init__(self, type)
        self.state['sequenceNumber'] = seqno
        self.data = ''

    def _data_url(self):
        return self.repl_url+'/'+self.type+'/'+self._path_frag()+'.osc.gz'

    def get(self, osmapi):
        '''Fetch and parse complete diff into a dictionary'''
        req = urllib2.Request(self._data_url())
        resp = urllib2.urlopen(req)
        data = gzip.GzipFile(fileobj=StringIO(resp.read())).read()
        self.data = osmapi.ParseOsc(data)

    def get_csets(self, osmapi):
        '''Fetch and parse diff to fetch changeset IDs only. More memory efficient than get()'''
        csets = []
        req = urllib2.Request(self._data_url())
        resp = urllib2.urlopen(req)
        dfile = gzip.GzipFile(fileobj=StringIO(resp.read()))
        for event, element in etree.iterparse(dfile):
            if element.tag in ['node', 'way', 'relation']:
                cid = int(element.attrib['changeset'])
                if cid not in csets:
                    csets.append(cid)
        return csets

    def get_data(self):
        return self.data

class State(Base):
    """OSM replication state"""
    def __init__(self, stype=None, autoload=True, seqno=None):
        Base.__init__(self, stype)
        self.set_sequenceno(seqno)
        self.autoload = autoload
        if autoload:
            self.load_state()

    def __str__(self):
        if (self.type=='day'):
            return 'daily, sequenceNo:'+str(self.sequenceno())+', timestamp:'+self.timestamp_str()
        else:
            return self.type+'ly, sequenceNo:'+str(self.sequenceno())+', timestamp:'+self.timestamp_str()

    def _state_url(self):
        if self.sequenceno()==None:
            return self.repl_url+self.type+'/state.txt'
        else:
            return self.repl_url+self.type+'/'+self._path_frag()+'.state.txt'

    def load_state(self):
        url = self._state_url()
        state = {}
        state['state url'] = url
        now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
        state['retrieved'] = now
        req = urllib2.Request(url)
        resp = urllib2.urlopen(req)
        logger.debug('urlopen code={}'.format(resp.getcode()))
        if resp.getcode() != 200:
            raise OsmDiffException('Unexpected return code:'+resp.getcode())
        tmp = resp.read()
        for line in tmp.splitlines():
            if len(line.split('=')) == 2:
                k, v = line.split('=')
                if k == 'sequenceNumber':
                    seq = int(v)
                    state[k] = seq
                elif k == 'timestamp':
                    v = v.replace('\:', ':')
                    ts = OsmDiffApi.timetxt2datetime(v)
                    state['timestamp_dt'] = ts
                    state[k] = v
                else:
                    state[k] = v
        needed_keys = ['timestamp_dt', 'sequenceNumber']
        if not set(needed_keys).issubset(state):
            raise OsmDiffException('Missing keys in state file, have {}'.format(state))
        self.state = state
