import sys
import datetime, pytz
import requests
import gzip
from StringIO import StringIO
import xml.etree.ElementTree as etree
import logging
import eventlet
import poly
import yaml

eventlet.monkey_patch()

logger = logging.getLogger(__name__)

class OsmDiffException(Exception):
    pass

class OsmDiffApi(object):
    OSM_TIMESTAMP_FMT = '%Y-%m-%dT%H:%M:%SZ'
    OSM_TIMESTAMP_FMT_CSET = '%Y-%m-%d %H:%M:%S.%f'

    def __init__(self, api='http://planet.osm.org'):
        #self.state_cache = {}
        #self.diff_cache = {}
        self.head_state = {}
        self.api = api
        self.netstat = [0,0] # rx, tx bytes
        
        # Non-simple below
        #self.update_head_state()

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
        """ Get most recent state object of a given type (changeset, day, hour or minute) """
        #if seqno==None and self.head_state.has_key(stype):
        #    return self.head_state[stype]
        #if seqno and self.state_cache.has_key(stype+str(seqno)):
        #    logger.debug("Getting cached state '"+stype+"' sequenceNo "+str(seqno)+" from cache")
        #    return self.state_cache[stype+str(seqno)]
        state = State(stype=stype, autoload=False, seqno=seqno)
        logger.debug("### Retrieving '"+stype+"' state, seqno "+str(state.sequenceno))
        state.load_state()
        #self.state_cache[stype+str(state.sequenceno)] = state
        logger.debug("Loaded state: "+str(state))
        return state

    def get_diff_from_state(self, state):
        return self.get_diff(state.sequenceno, state.type)

    def get_diff(self, seqno, type):
        diff = Diff(seqno, type)
        csets = diff.get_csets()
        return csets

    def get_cset_diff(self, seqno):
        diff = Diff(seqno, 'changesets')
        csets = diff.get_cset_diff()
        return csets

    def get_seqno_le_timestamp(self, type, timestamp, start, max_iter=None):
        """Get state object that has timestamp less than or equal to supplied
           timestamp. Searching back from supplied start object"""
        ptr = start
        seqno = ptr.sequenceno
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
        while ptr.timestamp() > timestamp and ptr.sequenceno != iter and seqno > 0:
            seqno -= 1
            ptr = self.get_state(type, seqno)
        if ptr.timestamp() > timestamp:
            return None
        return ptr

    @staticmethod
    def timetxt2datetime(ts):
        if isinstance(ts, datetime.datetime):
            return ts
        return datetime.datetime.strptime(ts, OsmDiffApi.OSM_TIMESTAMP_FMT).replace(tzinfo=pytz.utc)

class Base(object):
    repl_url = 'http://planet.osm.org/replication/'

    def __init__(self, type=None):
        self.state = {}
        if type == None:
            self.type = 'minute'
        else:
            self.type = type
        if type=='changesets':
            self.filetype = '.osm.gz'
            self.state_keys = {'yaml': ['timestamp_dt', 'sequence'], 'txt':  ['timestamp_dt', 'sequence']}
            self.state_txt_kv_split = ':'
            self.state_txt_ts_fmt = OsmDiffApi.OSM_TIMESTAMP_FMT_CSET
        else:
            self.filetype = '.osc.gz'
            self.state_keys = {'txt':  ['timestamp_dt', 'sequenceNumber']}
            self.state_txt_kv_split = '='
            self.state_txt_ts_fmt = OsmDiffApi.OSM_TIMESTAMP_FMT

    def _path_frag(self):
        seqno = self.sequenceno
        a = seqno/1000000
        b = (seqno/1000)%1000
        c = seqno % 1000
        return '{:03d}/{:03d}/{:03d}'.format(a,b,c)

    def timetxt2datetime(self, ts):
        if isinstance(ts, datetime.datetime):
            return ts
        return datetime.datetime.strptime(ts, self.state_txt_ts_fmt).replace(tzinfo=pytz.utc)

    def timestamp_str(self):
        return self.state['timestamp']

    def timestamp(self):
        return self.state['timestamp_dt']

    @property
    def sequenceno(self):
        if self.state.has_key('sequenceNumber'):
            return self.state['sequenceNumber']
        else:
            return None

    @sequenceno.setter
    def sequenceno(self, seqno):
        self.state['sequenceNumber'] = seqno


    def sequenceno_advance(self, offset=1):
        self.sequenceno = self.sequenceno+offset
        if self.autoload:
            self.load_state()

class Diff(Base):
    """OSM diff class"""
    def __init__(self, seqno, type=None):
        Base.__init__(self, type)
        self.state['sequenceNumber'] = seqno
        self.data = ''

    def _data_url(self):
        return self.repl_url+'/'+self.type+'/'+self._path_frag()+self.filetype

    def get_csets(self, timeout=50):
        '''Fetch and parse diff to fetch changeset. More memory efficient than get()'''
        csets = {}
        url = self._data_url()
        logger.debug('Fetching url {}'.format(url))
        with eventlet.Timeout(timeout):
            req = requests.get(url)
            if req.status_code!=200:
                raise OsmDiffException('Error fetching URL {}: {}:{}'.format(url,r.status_code,r.text))
            resp = req.content
            dfile = gzip.GzipFile(fileobj=StringIO(resp))
        logging.debug('Parsing diff {}, url {} (logger {})'.format(self.sequenceno, url, logger))
        now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
        for event, element in etree.iterparse(dfile):
            if element.tag == 'node':
                lat = float(element.attrib['lat'])
                lon = float(element.attrib['lon'])
            else:
                lat, lon = None, None
            if element.tag in ['node', 'way', 'relation']:
                cid = int(element.attrib['changesets'])
                if cid in csets:
                    if lat and lon:
                        csets[cid]['points_bbox'].add_point(lon, lat)
                else:
                    if lat and lon:
                        bbox = poly.BBox(lon, lat)
                    else:
                        bbox = poly.BBox()
                    csets[cid] = {'cid': cid,
                                  'source': {'type': self.type,
                                             'sequenceno': self.sequenceno,
                                             'observed': now},
                                  'points_bbox': bbox}
        return csets

    def get_cset_diff(self, timeout=50):
        '''Fetch and parse changeset diff'''
        csets = {}
        url = self._data_url()
        logger.debug('Fetching url {}'.format(url))
        with eventlet.Timeout(timeout):
            req = requests.get(url)
            if req.status_code!=200:
                raise OsmDiffException('Error fetching URL: {}:{}'.format(req.status_code,req.text,url))
            resp = req.content
            dfile = gzip.GzipFile(fileobj=StringIO(resp))
        logging.debug('Parsing diff {}, url {} (logger {})'.format(self.sequenceno, url, logger))
        now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
        for event, element in etree.iterparse(dfile):
            if element.tag == 'changeset':
                cid = int(element.attrib['id'])
                if 'min_lon' in element.attrib:
                    bbox = poly.BBox(float(element.attrib['min_lon']),
                                     float(element.attrib['min_lat']),
                                     float(element.attrib['max_lon']),
                                     float(element.attrib['max_lat']))
                else:
                    bbox = poly.BBox()
                csets[cid] = {'cid': cid,
                              'uid': int(element.attrib['uid']),
                              'user': element.attrib['user'],
                              'open': element.attrib['open'],
                              'comments_count': int(element.attrib['comments_count']),
                              'source': {'type': self.type,
                                         'sequenceno': self.sequenceno,
                                         'observed': now},
                              'bbox': bbox}
        return csets

    def get_data(self):
        return self.data

class State(Base):
    """OSM replication state"""
    def __init__(self, stype=None, autoload=True, seqno=None):
        Base.__init__(self, stype)
        self.sequenceno = seqno
        self.autoload = autoload
        if autoload:
            self.load_state()

    def __str__(self):
        if (self.type=='day'):
            return 'daily, sequenceNo:'+str(self.sequenceno)+', timestamp:'+self.timestamp_str()
        elif (self.type=='changesets'):
            return 'changeset, sequenceNo:'+str(self.sequenceno)+', timestamp:'+self.timestamp_str()
        else:
            return self.type+'ly, sequenceNo:'+str(self.sequenceno)+', timestamp:'+self.timestamp_str()

    def _state_url(self):
        postfix = 'txt'
        if self.sequenceno==None:
            if self.type == 'changesets':
                postfix = 'yaml'
            return self.repl_url+self.type+'/state.'+postfix
        else:
            return self.repl_url+self.type+'/'+self._path_frag()+'.state.'+postfix

    def load_state(self, timeout=10):
        if self.type == 'changesets' and self.sequenceno==None:
            return self.load_state_yaml(timeout)
        else:
            return self.load_state_txt(timeout)

    def load_state_yaml(self, timeout=10):
        url = self._state_url()
        state = {}
        state['state url'] = url
        now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
        state['retrieved'] = now
        with eventlet.Timeout(timeout):
            req = requests.get(url)
            if req.status_code!=200:
                raise OsmDiffException('Error fetching URL {}: {}:{}'.format(url,req.status_code,req.text))
            resp = req.content
        state = yaml.load(resp)
        if 'last_run' in state:
            state['timestamp'] = state['last_run'].isoformat()
            state['timestamp_dt'] = self.timetxt2datetime(state['last_run'])
        needed_keys = self.state_keys['yaml']
        if not set(needed_keys).issubset(state):
            raise OsmDiffException('Missing keys in state file, have {}, expected {}'.format(state.keys(), needed_keys))
        state['sequenceNumber'] = state['sequence']
        del state['sequence']
        self.state = state

    def load_state_txt(self, timeout=10):
        url = self._state_url()
        state = {}
        state['state url'] = url
        now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
        state['retrieved'] = now
        with eventlet.Timeout(timeout):
            req = requests.get(url)
            if req.status_code!=200:
                raise OsmDiffException('Error fetching URL {}: {}:{}'.format(url,req.status_code,req.text))
            resp = req.content
        for line in resp.splitlines():
            if len(line.split(self.state_txt_kv_split)) >= 2:
                k, v = line.split(self.state_txt_kv_split, 1)
                if k == 'sequenceNumber' or k == 'sequence':
                    seq = int(v)
                    state[k] = seq
                elif k == 'timestamp' or k == 'last_run':
                    v = v.replace('\:', ':').strip(' ')
                    v = v.rstrip('000 +00:00')
                    ts = self.timetxt2datetime(v)
                    state['timestamp_dt'] = ts
                    state['timestamp'] = v
                else:
                    state[k] = v
        needed_keys = self.state_keys['txt']
        if not set(needed_keys).issubset(state):
            raise OsmDiffException('Missing keys in state file, have {}, expected {}'.format(state.keys(), needed_keys))
        self.state = state
