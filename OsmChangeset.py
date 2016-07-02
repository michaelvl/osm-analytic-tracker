# -*- coding: utf-8 -*-

from osmapi import OsmApi
import OsmDiff
import pprint
import GeoJson as gj
import sys, time
import GeoTools
import logging
import datetime, pytz
import requests

logger = logging.getLogger(__name__)

class Timeout(Exception):
    pass

class Changeset(object):
    def __init__(self, id, api='https://api.openstreetmap.org'):
        self.id = id
        logger.debug('Using api={}'.format(api))
        self.osmapi = OsmApi(api=api)

        self.meta = None
        self.changes = None

        # History for modified/deleted elements, inner dicts indexed by object id
        self.history_one_version_back = True
        self.hist = {'node': {}, 'way':{}, 'relation':{}}

        # Summary of elemets, created, modified, deleted. '_' versions are summarized across all object types
        self.summary = {'create' : { 'node': 0, 'way':0, 'relation':0, 'relation_tags':{}},
                        'modify' : { 'node': 0, 'way':0, 'relation':0, 'relation_tags':{}},
                        'delete' : { 'node': 0, 'way':0, 'relation':0, 'relation_tags':{}},
                        '_create':0, '_modify':0, '_delete':0}
        # Tag changes
        self.tagdiff = self.getEmptyDiffDict()
        # Tags unchanged, i.e. mostly ID if object geometrically changed
        self.tags = {}
        # Simple (no tags) nodes
        self.simple_nodes = {'create':0, 'modify':0, 'delete':0}

        self.other_users = None
        self.mileage = None

        self.apidebug = False
        self.datadebug = False

    @staticmethod
    def get_timestamp(meta, typeof=None):
        if not typeof:
            if 'closed_at' in meta.keys():
                typeof = 'closed_at'
            else:
                typeof = 'created_at'

        cset_ts = meta[typeof]
        if type(cset_ts) is datetime.datetime:
            # Some osmapi's pass datetime's here without tz instead of a unicode string?
            timestamp = cset_ts.replace(tzinfo=pytz.utc)
        else:
            timestamp = osmdiff.OsmDiffApi.timetxt2datetime(cset_ts)
        return (typeof, timestamp)

    def printSummary(self):
        s = self.summary
        print '{} elements created: Nodes: {}, ways:{} Relations:{}'.format(s['_create'], s['create']['node'], s['create']['way'], s['create']['relation'])
        print '{} elements modified: Nodes: {}, ways:{} Relations:{}'.format(s['_modify'], s['modify']['node'], s['modify']['way'], s['modify']['relation'])
        print '{} elements deleted: Nodes: {}, ways:{} Relations:{}'.format(s['_delete'], s['delete']['node'], s['delete']['way'], s['delete']['relation'])
        print 'Simple nodes: {}'.format(pprint.pformat(self.simple_nodes))
        if (self.tagdiff['create'] or self.tagdiff['modify'] or self.tagdiff['delete']):
            print 'Tag change stats: {}'.format(pprint.pformat(self.tagdiff))
        else:
            print 'No tags changed'
        if self.other_users:
            print 'Modifies objects previously edited by: {}'.format(pprint.pformat(self.other_users))
        if self.mileage:
            print 'Mileage (ways): {} meters'.format(int(self.mileage['_all_create']-self.mileage['_all_delete']))
            print 'Mileage (navigable): {} meters'.format(int(self.mileage['_navigable_create']-self.mileage['_navigable_delete']))
            for nav_cat in self.mileage['by_type'].keys():
                for nav_type in self.mileage['by_type'][nav_cat].keys():
                    print 'Mileage ({}={}): {} meters'.format(nav_cat, nav_type,
                                                              int(self.mileage['by_type'][nav_cat][nav_type]))

    def printDiffs(self):
        self.buildDiffList()
        pprint.pprint(self.diffs)

    def _pluS(self, num):
        '''Return plural s'''
        if num==1:
            return ''
        return 's'

    def buildDiffList(self, maxtime=None):
        self.startProcessing(maxtime)
        self.diffs = self.getEmptyObjDict()
        for modif in self.changes:
            self.checkProcessingLimits()
            etype = modif['type']
            data = modif['data']
            id = data['id']
            version = data['version']
            action = modif['action']
            diff = self.getTagDiff(etype, id, version)
            label = self.getLabel(etype, id, version)
            #logger.debug('-- {} {} {} --'.format(action, etype, id))
            notes = []
            prev_authors = []
            entry = (action, label, diff, notes, prev_authors)
            self.diffs[etype][str(id)] = entry
            if action == 'modify':
                old = self.old(etype,id,version-1)
                if etype=='way':
                    nd_ops = self.diffStat(old['nd'], data['nd'])
                    if nd_ops or diff:
                        if nd_ops:
                            if nd_ops[0]:
                                notes.append(u'added {} node{}'.format(nd_ops[0], self._pluS(nd_ops[0])))
                            if nd_ops[1]:
                                notes.append(u'removed {} node{}'.format(nd_ops[1], self._pluS(nd_ops[1])))
                        if old['uid'] != data['uid']:
                            prev_authors.append(old['user'])
                if etype=='relation':
                    # member is list of dict's: {u'role': u'', u'ref': 1234, u'type': u'way'}
                    ombr = [x['ref'] for x in old['member']]
                    nmbr = [x['ref'] for x in data['member']]
                    m_ops = self.diffStat(ombr, nmbr)
                    if m_ops or diff:
                        if m_ops:
                            if m_ops[0]:
                                notes.append(u'added {} member{}'.format(m_ops[0], self._pluS(m_ops[0])))
                            if m_ops[1]:
                                notes.append(u'deleted {} member{}'.format(m_ops[1], self._pluS(m_ops[1])))
                        if old['uid'] != data['uid']:
                            prev_authors.append(old['user'])
                    if not m_ops and ombr!=nmbr:
                        notes.append(u'Reordered members')
                # TODO: Handle relation role changes (e.g. inner to outer)
                # TODO: Show relation as modified if member changes (e.g. way has added a node)
        return self.diffs

    def diffStat(self, a, b):
        ''' Given two lists of ids, return tuple with (added, removed) '''
        aa = set(a)
        bb = set(b)
        d1 = aa-bb
        d2 = bb-aa
        if not d1 and not d2:
            return None
        return (len(d2), len(d1))

    def downloadMeta(self, set_tz=True):
        if not self.meta:
            if self.apidebug:
                logger.debug('osmapi.ChangesetGet({}, include_discussion=True)'.format(self.id))
            self.meta = self.osmapi.ChangesetGet(self.id, include_discussion=True)
            if set_tz:
                for ts in ['created_at', 'closed_at']:
                    if ts in self.meta:
                        self.meta[ts] = self.meta[ts].replace(tzinfo=pytz.utc)
            if self.datadebug:
                logger.debug(u'meta({})={}'.format(self.id, self.meta))

    def downloadData(self):
        if not self.changes:
            if self.apidebug:
                logger.debug('osmapi.ChangesetDownload({})'.format(self.id))
            self.changes = self.osmapi.ChangesetDownload(self.id)
            if self.datadebug:
                logger.debug(u'changes({})={}'.format(self.id, self.changes))

    def downloadGeometry(self, overpass_api='https://overpass-api.de/api'):
        # https://overpass-api.de/api/interpreter?data=[adiff:"2016-07-02T22:23:17Z","2016-07-02T22:23:19Z"];(node(bbox)(changed);way(bbox)(changed););out meta geom(bbox);&bbox=11.4019207,55.8270254,11.4030363,55.8297091
        opened = self.get_timestamp(self.meta, 'created_at')[1] - datetime.timedelta(seconds=1)
        closed = self.get_timestamp(self.meta, 'closed_at')[1] + datetime.timedelta(seconds=1)
        tfmt = '%Y-%m-%dT%h:%M:%sZ'
        url = overpass_api+'/interpreter?data=[adiff:"'+ \
            opened.strftime(tfmt) + '","' + closed.strftime(tfmt) + \
            '"];(node(bbox)(changed);way(bbox)(changed););out meta geom(bbox);&bbox=' + \
            '{},{},{},{}'.format(self.meta['min_lon'], self.meta['min_lat'], self.meta['max_lon'], self.meta['max_lat'])
        #r = requests.get(url, stream=True, headers={'Connection':'close'})
        r = requests.get(url)
        if r.status_code!=200:
            raise Exception('Overpass error:{}:{}:{}'.format(r.status_code,r.text,url))
        #r.raw.decode_content = True
        print 'XX:'+r.text

    def startProcessing(self, maxtime=None):
        self.max_processing_time = maxtime
        self.processing_start = time.time()

    def checkProcessingLimits(self):
        if self.max_processing_time:
            used = time.time()-self.processing_start
            logger.debug('Used {:.2}s of {}s to process history'.format(used, self.max_processing_time))
            if used > self.max_processing_time:
                logger.warning('Timeout: Used {:.2}s of processing time'.format(used))
                raise Timeout

    def downloadHistory(self, maxtime=None):
        #pprint.pprint(self.changes)
        self.startProcessing(maxtime)
        for mod in self.changes:
            self.checkProcessingLimits()
            #print 'Modification:'
            #pprint.pprint(mod)
            self.getElement(mod)

    def unload(self):
        ch = self.changes
        self.changes = None
        del ch
        hist = self.hist
        self.hist = None
        del hist

    def wayIsNavigable(self, tags):
        navigable = ['highway', 'cycleway', 'busway']
        return set(navigable) & set(tags)

    def buildSummary(self, mileage=True, maxtime=None):
        self.startProcessing(maxtime)
        self.other_users = {}
        self.mileage = {'_navigable_create':0, '_navigable_delete':0, '_all_create':0, '_all_delete':0, 'by_type': {}}

        for modif in self.changes:
            self.checkProcessingLimits()
            etype = modif['type']
            data = modif['data']
            id = data['id']
            version = data['version']
            action = modif['action']

            self.summary['_'+action] += 1
            self.summary[action][etype] += 1

            diff = self.getTagDiff(etype, id, version)
            if diff:
                self.addDiffDicts(self.tagdiff, diff)

            self.tags = self.getTags(etype, id, version, self.tags)
            pprint.pprint(self.tags)
            if etype=='node':
                if action == 'delete':
                    old = self.old(etype,id,version-1)
                    if not diff and ('tag' not in old.keys() or not old['tag']):
                        self.simple_nodes[action] += 1
                else:
                    if not diff and ('tag' not in data.keys() or not data['tag']):
                        self.simple_nodes[action] += 1

            # For modify and delete we summarize affected users
            if action != 'create':
                old = self.old(etype,id,version-1)
                old_uid = old['uid']
                if old_uid != data['uid']:
                    old_uid = str(old_uid)
                    if not old_uid in self.other_users.keys():
                        if old['user']:
                            usr = old['user']
                        else:
                            usr = 'Anonymous'
                        self.other_users[old_uid] = {'user':usr, 'edits':0}
                    self.other_users[old_uid]['edits'] = +1

            # FIXME: Since we are only summing created/deleted ways, we ignore edited mileage
            if (action == 'create' or action == 'delete') and etype=='way':
                if action == 'create':
                    nv = -1 # If created, we take the latest node - in special cases where a node is edited multiple times in the same diff, this might not be correct
                else:
                    nv = data['timestamp']
                nd = data['nd']
                d = 0
                flon = flat = None
                for nid in nd:
                    n = self.old('node', nid, nv)
                    #logger.debug('({}, {})'.format(n['lon'], n['lat']))
                    if flon:
                        d += GeoTools.haversine(flon, flat, n['lon'], n['lat'])
                    flon, flat = (n['lon'], n['lat'])
                if action == 'delete':
                    d = -d
                self.mileage['_all_'+action] += d
                navigable = self.wayIsNavigable(data['tag'])
                if navigable:
                    self.mileage['_navigable_'+action] += d
                    nav_cat = navigable.pop()
                    nav_type = data['tag'][nav_cat]
                    if not nav_cat in self.mileage['by_type'].keys():
                        self.mileage['by_type'][nav_cat] = {}
                    if not nav_type in self.mileage['by_type'][nav_cat].keys():
                        self.mileage['by_type'][nav_cat][nav_type] = 0
                    self.mileage['by_type'][nav_cat][nav_type] += d
                #else:
                #    # Buildings, natural objects etc
                #    logger.debug('*** Not navigable way ({}) mileage: {} {} {}'.format(data['tag'], d, self.mileage, navigable))


    def getEmptyDiffDict(self):
        return {'create':{}, 'delete':{}, 'modify':{}}

    def getEmptyObjDict(self):
        return {'node':{}, 'way':{}, 'relation':{}}

    def addDiffDicts(self, into, src):
        for ac in src.keys():
            for k,v in src[ac].iteritems():
                into[ac][k] = into[ac].get(k, 0)+v

    def getTagDiff(self, etype, id, version):
        ''' Compute tag diffence between 'version' and previous version '''
        diff = self.getEmptyDiffDict()
        curr = self.old(etype,id,version)
        ntags = curr['tag']
        if version > 1:
            old = self.old(etype,id,version-1)
            otags = old['tag']
        else:
            old = None
            otags = {}
        #logger.debug('Tags curr:{}'.format(ntags))
        #logger.debug('Tags old:{}'.format(otags))
        for t in ntags.keys():
            if t in otags:
                if ntags[t]!=otags[t]:
                    k = u'{}={} --> {}={}'.format(t, otags[t], t, ntags[t])
                    diff['modify'][k] = diff['modify'].get(k, 0)+1
            else:
                k = u'{}={}'.format(t, ntags[t])
                diff['create'][k] = diff['create'].get(k, 0)+1
        for t in otags.keys():
            if not t in ntags:
                k = u'{}={}'.format(t, otags[t])
                diff['delete'][k] = diff['delete'].get(k, 0)+1
        if not diff['create'] and not diff['delete'] and not diff['modify']:
            return None
        return diff

    def getTags(self, etype, id, version, curr_tags=None):
        '''Compute unmodified tags, i.e. tags on objects changed geometrically, but
           where tags are identical between 'version' and previous version'''
        if not curr_tags:
            tags = {}
        else:
            tags = curr_tags
        curr = self.old(etype,id,version)
        ntags = curr['tag']
        if version > 1:
            old = self.old(etype,id,version-1)
            otags = old['tag']
        else:
            old = None
            otags = {}
        #logger.debug('Tags curr:{}'.format(ntags))
        #logger.debug('Tags old:{}'.format(otags))
        for t in ntags.keys():
            if t in otags:
                if ntags[t]==otags[t]:
                    k = u'{}={}'.format(t, ntags[t])
                    tags[k] = tags.get(k, 0)+1
        return tags

    def getLabel(self, etype, id, version):
        e = self.old(etype,id,version)
        if 'tag' in e.keys():
            tag = e['tag']
            if 'name' in tag.keys():
                label = u'name={}'.format(tag['name'])
            else:
                label = u'{}<{}>'.format(etype.capitalize(), id)
            keytags = ['highway', 'amenity', 'man_made', 'leisure', 'historic', 'landuse', 'type']
            for kt in keytags:
                if kt in tag.keys():
                    return u'{}={}, {}'.format(kt, tag[kt], label)
        return u'{}<{}>'.format(etype, id)

    # Note: Deleted objects only have history
    def getElement(self, modif):
        etype = modif['type']
        data = modif['data']
        id = data['id']
        version = data['version']
        action = modif['action']
        if action == 'create':
            self.hist[etype][id] = {1: data}
        else:
            e = self.old(etype, id, version-1)

    def getElementHistory(self, etype, id, version):
        logger.debug('GetElementHistory({} id {} version {})'.format(etype, id, version));
        hv = None
        if self.history_one_version_back or version<4:
            if not id in self.hist[etype].keys():
                self.hist[etype][id] = {}
            if self.apidebug:
                logger.debug('cset {} -> osmapi.{}Get({},ver={})'.format(self.id, etype.capitalize(), id, version))
            if etype == 'node':
                hv = self.osmapi.NodeGet(id, NodeVersion=version)
            elif etype == 'way':
                hv = self.osmapi.WayGet(id, WayVersion=version)
            elif etype == 'relation':
                hv = self.osmapi.RelationGet(id, RelationVersion=version)
            if hv:
                self.hist[etype][id][version] = hv
            else:
                # Possibly deleted element, fall-through
                logger.warning('Failed to get element history by version: {} id {} version {}'.format(etype, id, version))

        if not hv:
            if self.apidebug:
                logger.debug('cset {} -> osmapi.{}History({})'.format(self.id, etype.capitalize(), id))
            if etype == 'node':
                h = self.osmapi.NodeHistory(id)
            elif etype == 'way':
                h = self.osmapi.WayHistory(id)
            elif etype == 'relation':
                h = self.osmapi.RelationHistory(id)
            self.hist[etype][id] = h
            logger.debug('{} id {} history: {}'.format(etype, id, h))

    def old(self, etype, id, version, only_visible=True):
        logger.debug('Get old {} id {} version {}'.format(etype, id, version))
        if not isinstance(version, int):
            '''Support timestamp versioning. Ways and relations refer un-versioned
               nodes/ways/relations, i.e. if a way is deleted and the node it
               referred is moved subsequently, the deleted way should refer to
               the version existing when it was deleted.
            '''
            ts = OsmDiff.OsmDiffApi.timetxt2datetime(version)
            if self.apidebug:
                logger.debug('cset {} -> osmapi.{}History({})'.format(self.id, etype.capitalize(), id))
            if etype == 'node':
                self.hist[etype][id] = self.osmapi.NodeHistory(id)
            elif etype == 'way':
                self.hist[etype][id] = self.osmapi.WayHistory(id)
            elif etype == 'relation':
                self.hist[etype][id] = self.osmapi.RelationHistory(id)
            k = self.hist[etype][id].keys()
            k.sort(reverse=True)
            version = 1 # Default, if timestamps does not work - should never be needed
            for v in k:
                e = self.hist[etype][id][v]
                ets = OsmDiff.OsmDiffApi.timetxt2datetime(e['timestamp'])
                if ets<=ts:
                    version = e['version']
                    break;

        if version==-1:
            # Latest version we already have
            if id in self.hist[etype].keys():
                ks = self.hist[etype][id].keys()
                ks.sort()
                version = ks[-1]
                logger.debug('version -1 changed to {} (ks={})'.format(version, ks))
                for v in range(version, 1, -1):
                    if not only_visible or self.hist[etype][id][version]['visible']:
                        return self.hist[etype][id][version]
            logger.debug('Did not find existing history on {} id {} version {}'.format(etype, id, version))

        if (not id in self.hist[etype].keys()) or (not version in self.hist[etype][id].keys()):
            self.getElementHistory(etype, id, version)
            ks = self.hist[etype][id].keys()
            ks.sort()
            version = ks[-1]
            logger.debug('version -1 changed to {} (ks={})'.format(version, ks))

        logger.debug('{} id {} version {}: {}'.format(etype, id, version, self.hist[etype][id]))
        elem = self.hist[etype][id][version]

        if only_visible and not elem['visible']:
            if version > 1:
                # Deleted and then reverted elements will not have lat/lons on the old version
                logger.debug('Non-visible element found, trying {} id {} version {}'.format(etype, id, version-1))
                elem = self.old(etype, id, version-1, only_visible)
            else:
                logger.error('Non-visible element found: {} id {} version {}'.format(etype, id, version))

        if not ('uid' in elem.keys() and 'user' in elem.keys()):
            logger.warning('*** Warning, old element type={} id={} v={} elem={}'.format(etype, id, version, elem))
            # API-QUIRK (Anonymous edits, discontinued April 2009): Not all old
            # elements have uid. See
            # e.g. 'http://www.openstreetmap.org/api/0.6/way/8599635/history'
            # Also, 'created_by' does not seem like a complete substitute
            #if hasattr(elem, 'create_by'):
            #    user = '*unknown-created_by-{}*'.format(elem['create_by'])
            #else:
            user = None
            # Insert pseudo-values
            if not 'uid' in elem.keys():
                elem['uid'] = 0
            if not 'user' in elem.keys():
                elem['user'] = user
        return elem

    # def getReferencedElements(self):
    #     ''' Get elements referenced by changeset but not directly modified. '''
    #     for id,w in self.elems['way'].iteritems():
    #         self.getWay(id, w)
    #     for id,r in self.elems['relation'].iteritems():
    #         self.getRelation(id, r)

    # def getNode(self, id, data=None):
    #     if not data:
    #         if self.apidebug:
    #             logger.debug('osmapi.NodeGet({})'.format(id))
    #         data = self.osmapi.NodeGet(id)
    #     if not data: # Deleted, get history
    #         self.hist['node'][id] = self.osmapi.NodeHistory(id)
    #     else:
    #         self.elems['node'][id] = data

    # def getWay(self, id, data=None):
    #     if not data:
    #         if self.apidebug:
    #             logger.debug('osmapi.WayGet({})'.format(id))
    #         data = self.osmapi.WayGet(id)
    #     if not data: # Deleted, get history
    #         self.hist['way'][id] = self.osmapi.WayHistory(id)
    #     else:
    #         # Api has limitations on how many elements we can request in one multi-request
    #         # probably a char limitation, not number of ids
    #         api_max = 100
    #         all_nds = data['nd']
    #         for l in [all_nds[x:x+api_max] for x in xrange(0, len(all_nds), api_max)]:
    #             # We dont know node version - if node has been deleted we are in trouble
    #             if self.apidebug:
    #                 logger.debug('osmapi.NodesGet({})'.format(l))
    #             nds = self.osmapi.NodesGet(l)
    #             for nd in nds.keys():
    #                 self.getNode(nd, nds[nd])

    # def getRelation(self, id, data=None):
    #     if not data:
    #         if self.apidebug:
    #             logger.debug('osmapi.RelationGet({})'.format(id))
    #         data = self.osmapi.RelationGet(id)
    #     if not data: # Deleted, get history
    #         self.hist['relation'][id] = self.osmapi.RelationHistory(id)
    #     else:
    #         for mbr in data['member']:
    #             ref = mbr['ref']
    #             etype = mbr['type']
    #             # We dont know version - if way/node has been deleted we are in trouble
    #             if etype == 'node':
    #                 self.getNode(ref)
    #             elif etype == 'way':
    #                 self.getWay(ref)
    #             elif etype == 'relation':
    #                 self.getRelation(ref)

    def isInside(self, area, load_way_nodes=True):
        '''Return true if there are node edits in changeset and one or more nodes are within area'''
        hasnodes = False
        for modif in self.changes:
            etype = modif['type']
            data = modif['data']
            action = modif['action']
            if etype=='node':
                hasnodes = True
                if action!='delete':
                    if area.contains(data['lon'], data['lat']):
                        return True
                else:
                    # Deleted node do not have lat/lon
                    id = data['id']
                    version = data['version']
                    n = self.old(etype,id,version-1)
                    if area.contains(n['lon'], n['lat']):
                        return True
        if hasnodes:
            # Changesset has node edits, but none inside area i.e. most likely
            # not within area. We could have way/relation changes inside area,
            # which we will miss (FIXME).
            return False
        else:
            # FIXME: We really do not know because only tags/members on/off
            # ways/relations where changes. Maybe download way/relation nodes
            # to detect where edit where
            if load_way_nodes:
                for modif in self.changes:
                    etype = modif['type']
                    data = modif['data']
                    #action = modif['action']
                    if etype=='way':
                        nd = data['nd']
                        for nid in nd:
                            n = self.old('node', nid, data['timestamp'])
                            if area.contains(n['lon'], n['lat']):
                                return True
                return False
            else:
                # If we do not load nodes, we assume there are changed within area
                return True

    def getGeoJsonDiff(self, include_modified_ways=True):
        #self.getReferencedElements()
        g = gj.GeoJson()
        c_create = '009a00' # Green
        c_delete = 'ff2200' # Red
        c_old = 'ffff60'    # Yellow
        c_mod = '66aacc'    # Light blue

        for modif in self.changes:
            etype = modif['type']
            n = modif['data']
            id = n['id']
            version = n['version']
            action = modif['action']
            #diff = self.getTagDiff(etype, id, version)
            f = None
            if action=='delete':
                e = self.old(etype,id,version-1)
            else:
                e = self.old(etype,id,version)
            if etype=='node':
                if action=='modify':
                    oe = self.old(etype,id,version-1)
                    logger.debug('Modify node {} version={} e={}, oe={}'.format(id, version, e, oe))
                    l = g.addLineString()
                    g.addLineStringPoint(l, e['lon'], e['lat'])
                    g.addLineStringPoint(l, oe['lon'], oe['lat'])
                    g.addColour(l, c_old)
                    g.addProperty(l, 'popupContent', 'Node moved')
                    g.addProperty(l, 'action', action)
                    g.addProperty(l, 'type', etype)

                    #f = g.addPoint(oe['lon'], oe['lat'])
                    #g.addColour(f, c_old)
                    f = g.addPoint(e['lon'], e['lat'])
                else:
                    f = g.addPoint(e['lon'], e['lat'])
            if etype=='way' and (include_modified_ways or action!='modify'):
                f = g.addLineString()
                nd = e['nd']
                for nid in nd:
                    # Using timestamp here means we draw the old way. If
                    # existing points have been moved and new ones added, we
                    # will draw the old way but show points as being moved.
                    n = self.old('node', nid, e['timestamp'])
                    g.addLineStringPoint(f, n['lon'], n['lat'])

            if f:
                # Popup text
                txt = ''

                e = self.old(etype,id,version)
                tag = e['tag']

                g.addProperty(f, 'action', action)
                g.addProperty(f, 'type', etype)
                g.addProperty(f, 'id', id)
                if action=='delete':
                    g.addColour(f, c_delete)
                    g.addProperty(f, 'tag', {version: tag})
                elif action=='create':
                    g.addColour(f, c_create)
                    g.addProperty(f, 'tag', {version: tag})
                else:
                    g.addColour(f, c_mod)
                    oe = self.old(etype,id,version-1)
                    g.addProperty(f, 'tag', {version: tag, version-1: oe['tag']})

                if self.diffs:
                    diff = self.diffs[etype][str(id)]
                    if diff:
                        if action!='create': # Dont show tags twice
                            d = diff[2]
                            if d:
                                tags = 0
                                repl = {'create': 'Added tags:', 'modify': 'Modified tags:', 'delete': 'Removed tags:'}
                                for k in ['create', 'modify', 'delete']:
                                    if len(d[k].keys()) > 0:
                                        txt = self.joinTxt(txt, repl[k])
                                    for kk in d[k].keys():
                                        txt = self.joinTxt(txt, kk)
                                    tags += 1
                                if tags > 0:
                                    txt = self.joinTxt(txt, '', new_ph=True)

                        notes = diff[3]
                        if notes:
                            for n in notes:
                                txt = self.joinTxt(txt, n)
                            txt = self.joinTxt(txt, '', new_ph=True)

                        usr = diff[4]
                        if usr:
                            txt = self.joinTxt(txt, u'Affects edits by:', new_ph=True)
                            for u in usr:
                                if not u:
                                    u = '(Anonymous)'
                                txt = self.joinTxt(txt, u)

                if txt != '':
                    txt = self.joinTxt(txt, '')
                    g.addProperty(f, 'popupContent', txt)

        return g.getData()

    def joinTxt(self, t1, t2, new_ph=False, pstart='<p>', pend='</p>'):
        if (t1=='' or t1.endswith(pend)) and t2!='':
            t1 += pstart+t2.capitalize()
        else:
            if t2=='':
                t1+=pend
            else:
                if new_ph:
                    if t1!='':
                        t1 += '.'+pend
                    t1 += pstart+t2.capitalize()
                else:
                    if not t1.endswith(':'):
                        t1 += ', '
                    t1 += t2
        return t1
