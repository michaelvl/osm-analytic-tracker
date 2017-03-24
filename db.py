#!/usr/bin/env python

import sys
import pprint
import argparse
import logging
import pymongo
from bson.json_util import dumps, loads
from bson.codec_options import CodecOptions
import datetime, pytz
import osm.diff

logger = logging.getLogger('db')

class DataBase(object):
    STATE_NEW = 'NEW'
    STATE_BOUNDS_CHECK = 'BOUNDS_CHECK'     # Used for combined bounds and regex filtering
    STATE_BOUNDS_CHECKED = 'BOUNDS_CHECKED' # Cset passed filter
    STATE_ANALYZING1 = 'ANALYZING1'         # Initial processing (meta etc)
    STATE_OPEN = 'OPEN'                     # Wait state
    STATE_CLOSED = 'CLOSED'                 # Staging state for deep analysis
    STATE_ANALYZING2 = 'ANALYZING2'         # Deeper analysis of closed csets
    STATE_REANALYZING = 'REANALYZING'       # Updates (notes etc)
    STATE_DONE = 'DONE'                     # For now, all analysis completed
    STATE_QUARANTINED = 'QUARANTINED'       # Temporary error experienced
    
    def __init__(self, url='mongodb://localhost:27017/', admin=False):
        self.url = url
        self.client = pymongo.MongoClient(url)
        self.db = pymongo.database.Database(self.client, 'osmtracker', codec_options=CodecOptions(tz_aware=True))
        self.ctx = self.db.context
        self.csets = self.db.chgsets
        self.all_states = [STATE_NEW, STATE_BOUNDS_CHECK, STATE_BOUNDS_CHECKED,
                           STATE_ANALYZING1, STATE_OPEN, STATE_CLOSED,STATE_ANALYZING2,
                           STATE_REANALYZING, STATE_DONE, STATE_QUARANTINED]
        if admin:
            self.csets.create_index('state')
            self.csets.create_index([('updated', pymongo.DESCENDING)])
            self.csets.create_index([('state', pymongo.ASCENDING),('state_changed', pymongo.DESCENDING)])
            self.csets.create_index([('state', pymongo.ASCENDING),('updated', pymongo.DESCENDING)])
            self.csets.create_index([('state', pymongo.ASCENDING),('refreshed', pymongo.DESCENDING)])

    def __str__(self):
        return self.url
        
    def drop(self, drop_ctx=True, drop_chgsets=True):
        if drop_ctx:
            cnt = self.ctx.pointer.delete_many({}).deleted_count
            cnt = self.ctx.generation.delete_many({}).deleted_count
            logger.debug('Deleted context')
        if drop_chgsets:
            cnt = self.chgsets.delete_many({}).deleted_count
            logger.debug('Deleted {} changesets from work queue'.format(cnt))

    def pointer_meta_update(self, _dict):
        self.ctx.pointer.update({u'_id':0}, {'$set': _dict}, upsert=True)

    @property
    def pointer(self):
        return self.ctx.pointer.find_one({u'_id':0})

    @pointer.setter
    def pointer(self, ptr):
        if type(ptr) is int:
            ptr = osm.diff.State(seqno=ptr)
        if type(ptr) is osm.diff.State:
            ptr = {u'stype': ptr.type,
                   u'seqno': ptr.sequenceno,
                   u'timestamp': ptr.timestamp() }
        else:
            raise TypeError
        if not self.pointer:
            ptr['first_pointer'] = dict(ptr)
        self.pointer_meta_update(ptr)

    def pointer_advance(self, offset=1):
        old = self.ctx.pointer.find_one_and_update({u'_id':0}, {'$inc': {u'seqno': offset}})
        logger.debug('Old pointer before advance by {}: {}'.format(offset, old))

    @property
    def generation(self):
        gen = self.ctx.generation.find_one({u'_id':0})
        if not gen:
            return None
        return gen['no']

    @generation.setter
    def generation(self, no):
        gen = {u'no': no}
        self.ctx.generation.update({u'_id':0}, {'$set': gen}, upsert=True)

    def generation_advance(self, offset=1):
        if not self.generation:
            self.generation = 0
        old = self.ctx.generation.find_one_and_update({u'_id':0}, {'$inc': {u'no': offset}})
        logger.debug('Old generation before advance by {}: {}'.format(offset, old))

    @property
    def chgsets(self):
        return self.csets

    def chgsets_count(self):
        return self.csets.count()

    def chgsets_find_selector(self, state=STATE_DONE, before=None, after=None, timestamp='updated'):
        sel = dict()
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
    
    def chgsets_find(self, state=STATE_DONE, before=None, after=None, timestamp='updated', sort=True):
        sel = self.chgsets_find_selector(state, before, after, timestamp)
        if sort:
            cursor = self.csets.find(sel).sort(timestamp, pymongo.DESCENDING)
        else:
            cursor = self.csets.find(sel)

        # FIXME: Depends on mongodb version!
        # expl = cursor.explain('executionStats')
        # millis = None
        # nscanned = None
        # if 'executionStats' in expl:
        #     millis = expl['executionStats']['executionTimeMillis']
        #     nscanned = expl['executionStats']['totalKeysExamined']
        # else:
        #     millis = expl['millis']
        #     nscanned = expl['nscanned']
        # if millis and millis>500:
        #     logger.warn("DB selector {} find explain: {}".format(sel, expl))
        # logger.info("DB lookup took {}ms, scanned {} objects, selector={}".format(millis, nscanned, sel))
        return cursor

    def chgset_append(self, cid, source=None):
        now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
        c = {'_id': cid, u'cid': cid,
             'state': self.STATE_NEW,
             'labels': [],
             'queued': now,
             'updated': now,   # Last time csets content changed
             'refreshed': now, # Last attempt at refresh meta (for e.g. notes)
             'state_changed': now}
        if source:
            c[u'source'] = source
        self.csets.replace_one({'_id':cid}, c, upsert=True)

    # TODO: Use chgsets_find_selector()
    def chgset_start_processing(self, istate, nstate, before=None, after=None, timestamp='state_changed'):
        '''Start a processing of a changeset with state istate and set intermediate state nstate''' 
        now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
        sel = {}
        if type(istate) is list:
            sel['state'] = {'$in': istate}
        else:
            sel['state'] = istate
        if before or after:
            sel[timestamp] = {}
        if before:
            sel[timestamp]['$lt'] = before
        if after:
            sel[timestamp]['$gt'] = after
        c = self.csets.find_one_and_update(
            sel,
            {'$set': {'state': nstate,
                      'state_changed': now}},
            sort=[('queued', pymongo.DESCENDING)],
            return_document=pymongo.ReturnDocument.AFTER)
        if c:
            logger.debug('Start processing: {}'.format(c))
            return c
        else:
            logger.debug('No csets available for processing from state {}'.format(istate))
            return None

    def chgset_drop(self, cid):
        cnt = self.csets.delete_one({'_id': cid})
        if cnt==0:
            logger.error('Error dropping cset {}'.format(cid))
        else:
            logger.debug('Dropped cset {}'.format(cid))

    def chgset_processed(self, c, state, failed=False, refreshed=False):
        now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
        cid = c['cid']
        setter = {'$set': {'state': state,
                           'state_changed': now}}
        if refreshed:
            setter['$set']['refreshed'] = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
        if 'meta' in c:
            meta = loads(c['meta'])
            setter['$set']['updated'] = osm.changeset.Changeset.get_timestamp(meta, include_discussion=True)[1]

        if 'labels' in c:
            setter['$set']['labels'] = c['labels']
        c = self.csets.update_one(
            {'_id': cid}, setter)
        if failed:
            logger.error('Failed processing cset {}'.format(cid))
        else:
            logger.debug('Done processing cset {}'.format(cid))
        if state==self.STATE_DONE:
            logger.debug('New generation due to cset state DONE, cid={}'.format(cid))
            self.generation_advance()

    def chgset_update_timestamp(self, cid, timestamp='updated'):
        c = self.csets.update_one(
            {'_id': cid},
            {'$set': {timestamp: datetime.datetime.utcnow().replace(tzinfo=pytz.utc)}})

    def chgset_set_meta(self, cid, meta):
        old_meta = self.chgset_get_meta(cid)
        if old_meta:
            if not self.dict_changed(old_meta, meta):
                logger.debug('Setting meta for cset {}, but nothing changed'.format(cid))
                return False
        _meta = dumps(meta) # OSM changeset tags may contain unicode
        logger.debug('Setting meta for cset {}: {}'.format(cid, pprint.pformat(meta)))
        now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc) #FIXME: From cset
        self.csets.update_one({'_id':cid}, {'$set':
                                            {'meta': _meta,
                                             'updated': now}}, upsert=True)
        return True

    # FIXME: Refactor and remove
    def chgset_get_meta(self, cid):
        cset = self.csets.find_one({'_id':cid})
        if not cset or not 'meta' in cset:
            return None
        return loads(cset['meta'])

    def chgset_set_info(self, cid, info):
        old_info = self.chgset_get_info(cid)
        if old_info:
            if not self.dict_changed(old_info, info):
                logger.debug('Setting info for cset {}, but nothing changed'.format(cid))
                return False
        _info = dumps(info) # Changeset info may contain unicode
        logger.debug('Setting info for cset {}: {}'.format(cid, pprint.pformat(info)))
        now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc) #FIXME: From cset
        self.csets.update_one({'_id':cid}, {'$set':
                                            {'info': _info,
                                             'updated': now}}, upsert=True)
        return True

    # FIXME: Refactor and remove
    def chgset_get_info(self, cid):
        cset = self.csets.find_one({'_id':cid})
        if not cset or not 'info' in cset:
            if not cset:
                logger.warn('Cset cid={} not found'.format(cid))
            else:
                logger.warn('Cset has no info, keys: {}'.format(cset.keys()))
            return None
        return loads(cset['info'])

    def dict_changed(self, old, new):
        logger.debug('Compare old: {}'.format(old))
        logger.debug('Compare new: {}'.format(new))
        def subcompare(old, new):
            for k in old:
                if k not in new:
                    logger.debug('Dict change: k={} not present'.format(k))
                    return True
                elif type(old[k])==dict and type(new[k])==dict:
                    if subcompare(old[k], new[k]):
                        logger.debug('Dict change: k={} v=dict'.format(k))
                        return True
                elif old[k]!=new[k]:
                    logger.debug('Dict change: k={} v_old={}, v_new={}'.format(k,old[k],new[k]))
                    return True
        if subcompare(old, new) or subcompare(new, old):
            return True
        return False

def drop(args, db):
    if args.timeout:
        now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
        dt = now-datetime.timedelta(seconds=1200)
        states = [db.STATE_NEW, db.STATE_BOUNDS_CHECK, db.STATE_ANALYZING1,
                  db.STATE_ANALYZING2, db.STATE_REANALYZING]
        selector = db.chgsets_find_selector(state=states, before=dt, after=None,
                                            timestamp='state_changed')
        if args.cid:
            selector['cid'] = args.cid
        for c in db.chgsets.find(selector):
            logger.info('Dropping cset {}'.format(c['cid']))
            db.chgset_drop(c['cid'])
    else:
        if args.cid:
            db.chgset_drop(args.cid)
        else:
            db.drop()

def show_brief(args, db, reltime=True):
    print 'CsetID   State          Queued          StateChanged    Updated         Refreshed       User :: Comment'
    for c in db.chgsets_find(state=None):
        if not args or ((not args.cid or args.cid==c['cid']) and (args.new or c['state']!=db.STATE_NEW)):
            cid = c['cid']
            if reltime:
                def ts(dt):
                    now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
                    df = now-dt
                    return u'{:.2f}s ago'.format(df.total_seconds())
            else:
                def ts(dt):
                    return dt.strftime('%Y:%m:%d %H:%M:%S')
            if c['state'] != 'NEW' and c['state'] != 'BOUNDS_CHECK' and c['state'] != 'ANALYZING1':
                meta = db.chgset_get_meta(cid)
                if not meta:
                    logger.error('No meta found for cid {}: {}'.format(cid, c))
                else:
                    logger.debug('cset={}, meta: {}'.format(c, meta))
                    if 'comment' in meta['tag']:
                        comment = meta['tag']['comment']
                    else:
                        comment = '*no comment*'
                    print u'{:8} {:14} {:15} {:15} {:15} {:15} {} :: {}'.format(cid, c['state'], ts(c['queued']), ts(c['state_changed']), ts(c['updated']), ts(c['refreshed']), meta['user'], comment).encode('ascii', errors='backslashreplace')
            else:
                print u'{:8} {:14} {:15} {:15}'.format(cid, c['state'], ts(c['queued']), ts(c['state_changed'])).encode('ascii', errors='backslashreplace')

def show(args, db):
    print '-- Pointer: -----------'
    pprint.pprint(db.pointer)
    print '-- Generation:', db.generation
    if args.brief:
        show_brief(args, db)
    else:
        print '-- Changesets: ({} csets) -----------'.format(db.chgsets.count())
        for c in db.chgsets.find():
            if (not args.cid or args.cid==c['cid']) and (args.new or c['state']!=db.STATE_NEW):
                print '  cid={}: {}'.format(c['cid'], pprint.pformat(c))

def do_reanalyze(db, now, selector, newstate):
    logger.debug('Reanalyze selector: {}'.format(selector))
    cnt = db.chgsets.update_many(selector,
                                 {'$set': {'state': newstate,
                                           'state_changed': now}}).modified_count
    logger.warn('Re-scheduled {} csets for analysis (new state {})'.format(cnt, newstate))

def reanalyze(args, db):
    now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
    if args.timeout:
        dt = now-datetime.timedelta(seconds=1200)
        states = [db.STATE_ANALYZING1, db.STATE_ANALYZING2, db.STATE_REANALYZING]
        selector = db.chgsets_find_selector(state=states, before=dt, after=None, timestamp='state_changed')
        if args.cid:
            selector['cid'] = args.cid
        do_reanalyze(db, now, selector, db.STATE_BOUNDS_CHECKED)

        states = [db.STATE_BOUNDS_CHECK]
        selector = db.chgsets_find_selector(state=states, before=dt, after=None, timestamp='state_changed')
        if args.cid:
            selector['cid'] = args.cid
        do_reanalyze(db, now, selector, db.STATE_NEW)
    else:
        newstate = db.STATE_BOUNDS_CHECKED
        if args.new:
            newstate = db.STATE_NEW
        states = [db.STATE_BOUNDS_CHECK, db.STATE_ANALYZING1, db.STATE_OPEN,
                  db.STATE_CLOSED, db.STATE_ANALYZING2, db.STATE_REANALYZING, db.STATE_DONE]
        selector = {'state': {'$in': states}}
        if args.cid:
            selector['cid'] = args.cid

        do_reanalyze(db, now, selector, newstate)

def ptrset(args, db):
    db.pointer = args.seqno

def main(argv):
    parser = argparse.ArgumentParser(description='OSM tracker database tool')
    parser.add_argument('-l', dest='log_level', default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Set the log level')
    parser.add_argument('--dburl', dest='dburl', default='mongodb://localhost:27017/')
    subparsers = parser.add_subparsers()

    parser_drop = subparsers.add_parser('drop')
    parser_drop.set_defaults(func=drop)
    parser_drop.add_argument('--cid', type=int, default=None, help='Changeset ID')
    parser_drop.add_argument('--timeout', action='store_true', default=False, help='Drop timed-out csets only')

    parser_show = subparsers.add_parser('show')
    parser_show.set_defaults(func=show)
    parser_show.add_argument('--cid', type=int, default=None, help='Changeset ID')
    parser_show.add_argument('--brief', action='store_true', default=False, help='Show less information')
    parser_show.add_argument('--new', action='store_true', default=False, help='Show changesets in NEW state')

    parser_reanalyze = subparsers.add_parser('reanalyze')
    parser_reanalyze.set_defaults(func=reanalyze)
    parser_reanalyze.add_argument('--cid', type=int, default=None, help='Changeset ID')
    parser_reanalyze.add_argument('--new', action='store_true', default=False, help='Reset states to NEW')
    parser_reanalyze.add_argument('--timeout', action='store_true', default=False, help='Perform timeout check only')
    parser_reanalyze.add_argument('--hard', action='store_true', default=False, help='Re-analyze changesets already fully analyzed. Default is only re-analyze those that are partially analyzed.')

    parser_ptrset = subparsers.add_parser('ptrset')
    parser_ptrset.set_defaults(func=ptrset)
    parser_ptrset.add_argument('--seqno', type=int, required=True, help='Minutely sequence number')

    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level, None))

    db = DataBase(args.dburl)
    
    return args.func(args, db)

if __name__ == "__main__":
   sys.exit(main(sys.argv[1:]))
