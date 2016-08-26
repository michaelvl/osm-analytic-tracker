#!/usr/bin/python

import sys
import pprint
import argparse
import logging
import pymongo
from bson.json_util import dumps, loads
from bson.codec_options import CodecOptions
import datetime, pytz
import OsmDiff

logger = logging.getLogger('db')

class DataBase(object):
    STATE_NEW = 'NEW'
    STATE_BOUNDS_CHECK = 'BOUNDS_CHECK'
    STATE_BOUNDS_CHECKED = 'BOUNDS_CHECKED'
    STATE_ANALYZING1 = 'ANALYZING1'
    STATE_OPEN = 'OPEN'
    STATE_CLOSED = 'CLOSED'
    STATE_ANALYZING2 = 'ANALYZING2'
    STATE_REANALYZING = 'REANALYZING'
    STATE_DONE = 'DONE'
    
    def __init__(self, url='mongodb://localhost:27017/'):
        self.url = url
        self.client = pymongo.MongoClient(url)
        #self.db = self.client.osmtracker
        self.db = pymongo.database.Database(self.client, 'osmtracker', codec_options=CodecOptions(tz_aware=True))
        self.ctx = self.db.context
        self.csets = self.db.chgsets
        self.csets.create_index('state')
        self.csets.create_index([('state', pymongo.ASCENDING),('state_changed', pymongo.DESCENDING)])
        self.csets.create_index([('state', pymongo.ASCENDING),('updated', pymongo.DESCENDING)])
        self.csets.create_index([('state', pymongo.ASCENDING),('refreshed', pymongo.DESCENDING)])
        logger.debug(self.client.database_names())

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
            ptr = OsmDiff.State(seqno=ptr)
        if type(ptr) is OsmDiff.State:
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

    def chgsets_find_selector(self, state=STATE_DONE, before=None, after=None, timestamp='updated'):
        if type(state) is list:
            sel = {'state': {'$in': state}}
        else:
            sel = {'state': state}
        if before or after:
            sel[timestamp] = {}
        if before:
            sel[timestamp]['$lt'] = before
        if after:
            sel[timestamp]['$gt'] = after
        return sel
    
    def chgsets_find(self, state=STATE_DONE, before=None, after=None, timestamp='updated', sort=True):
        sel = self.chgsets_find_selector(state, before, after, timestamp)
        if sort:
            return self.csets.find(sel).sort(timestamp, pymongo.DESCENDING)
        else:
            return self.csets.find(sel)

    def chgset_append(self, cid, source=None):
        now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
        c = {'_id': cid, u'cid': cid,
             'state': self.STATE_NEW,
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
                #self.meta.update_one(
                #    {'_id': cid},
                #    {'$set': {'timestamp': datetime.datetime.utcnow().replace(tzinfo=pytz.utc)}})
                return False
        _meta = dumps(meta) # OSM changeset tags may contain unicode
        logger.debug('Setting meta for cset {}: {}'.format(cid, pprint.pformat(meta)))
        now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc) #FIXME: From cset
        self.csets.update_one({'_id':cid}, {'$set':
                                            {'meta': _meta,
                                             'updated': now}}, upsert=True)
        self.generation_advance()
        return True

    # FIXME: Refactor and remove
    def chgset_get_meta(self, cid):
        cset = self.csets.find_one({'_id':cid})
        if not 'meta' in cset:
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
        self.generation_advance()
        return True

    # FIXME: Refactor and remove
    def chgset_get_info(self, cid):
        cset = self.csets.find_one({'_id':cid})
        if not 'info' in cset:
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
    if args.cid:
        db.chgset_drop(args.cid)
    else:
        db.drop()

def show_brief(args, db):
    print 'CsetID   State          Queued          StateChanged    Updated         Refreshed       User :: Comment'
    for c in db.chgsets.find():
        cid = c['cid']
        def ts(dt):
            now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
            df = now-dt
            return u'{:.2f}s ago'.format(df.total_seconds())
        if c['state'] != 'NEW' and c['state'] != 'BOUNDS_CHECK' and c['state'] != 'ANALYZING1':
            meta = db.chgset_get_meta(cid)
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
            if not args.cid or args.cid==c['cid']:
                print '  cid={}: {}'.format(c['cid'], pprint.pformat(c))

def reanalyze(args, db):
    now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
    newstate = db.STATE_BOUNDS_CHECKED
    if args.new:
        newstate = db.STATE_NEW
    if args.timeout:
        states = [db.STATE_BOUNDS_CHECK, db.STATE_ANALYZING1, db.STATE_ANALYZING2, db.STATE_REANALYZING]
        dt = now-datetime.timedelta(seconds=1200)
        selector = db.chgsets_find_selector(state=states, before=dt, after=None, timestamp='state_changed')
    else:
        states = [db.STATE_BOUNDS_CHECK, db.STATE_ANALYZING1, db.STATE_OPEN,
                  db.STATE_CLOSED, db.STATE_ANALYZING2, db.STATE_REANALYZING, db.STATE_DONE]
        selector = {'state': {'$in': states}}
    if args.cid:
        selector['cid'] = args.cid

    logger.debug('Reanalyze selector: {}'.format(selector))
    cnt = db.chgsets.update_many(selector,
                                 {'$set': {'state': newstate,
                                           'state_changed': now}}).modified_count
    print 'Re-scheduled {} csets for analysis (state {})'.format(cnt, newstate)

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

    parser_show = subparsers.add_parser('show')
    parser_show.set_defaults(func=show)
    parser_show.add_argument('--cid', type=int, default=None, help='Changeset ID')
    parser_show.add_argument('--brief', action='store_true', default=False, help='Show less information')

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
