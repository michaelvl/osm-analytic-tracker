#!/usr/bin/python

import sys, time
import argparse
import osmapi
import OsmChangeset
import Poly
import json, pickle
import OsmDiff as osmdiff
import datetime, pytz
import pprint
import logging, logging.config
import db as database
import config as configfile
import importlib
import ColourScheme as col
import HumanTime
import operator
import urllib2, socket
import traceback

logger = logging.getLogger('osmtracker')

def fetch_and_process_diff(config, dapi, seqno, ctype, area=None):
    chgsets = dapi.get_diff_csets(seqno, ctype)
    return chgsets

def cset_check_bounds(args, config, area, cid, debug=0, strict_inside_check=True):
    # Read changeset meta and check if within area
    c = OsmChangeset.Changeset(cid, api=config.get('osm_api_url','tracker'))
    c.apidebug = debug
    c.datadebug = debug
    c.downloadMeta()

    # Check if node and thus changeset is within area (bbox check)
    #pprint.pprint(c.meta)
    if not area or area.contains_chgset(c.meta):
        if strict_inside_check:
            c.downloadData()
            if c.isInside(area):
                return c
        else:
            return c
    return None

def cset_refresh_meta(args, config, db, cset, no_delay=False):
    cid = cset['cid']
    timeout_s = config.get('refresh_meta_minutes', 'tracker')*60
    refresh = no_delay
    if timeout_s>0:
        now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
        last_refresh = db.chgset_get_meta_meta(cid)['timestamp']
        age_s = (now-last_refresh).total_seconds()
        if age_s > timeout_s:
            logger.debug('Refresh meta due to age {}s, timeout {}s'.format(age_s, timeout_s))
            refresh = True
    if refresh:
        logger.debug('Refresh meta for cid {} (no_delay={})'.format(cid, no_delay))
        c = OsmChangeset.Changeset(cid, api=config.get('osm_api_url','tracker'))
        c.downloadMeta()
        old_meta = db.chgset_get_meta(cid)
        return db.chgset_set_meta(cid, c.meta)
    return False

def cset_process_local1(args, config, db, cset, info):
    '''Preprocess cset, i.e. locally compute various information based on meta, tag
       info or other data.
    '''
    cid = cset['cid']
    meta = db.chgset_get_meta(cid)

    if not 'misc' in info:
        misc = {}
        info['misc'] = misc
        user = meta['user']
        colours = col.ColourScheme(seed=0)
        misc['user_colour'] = colours.get_colour(user)
    else:
        misc = info['misc']

    if cset_refresh_meta(args, config, db, cset, no_delay=('timestamp_type' not in misc)) or 'timestamp_type' not in misc:
        (tstype, timestamp) = OsmChangeset.Changeset.get_timestamp(meta)
        ts_type2txt = { 'created_at': 'Started', 'closed_at': 'Closed' }
        misc['timestamp_type'] = tstype
        misc['timestamp_type_txt'] = ts_type2txt[tstype]
        misc['timestamp'] = timestamp

    now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
    observed_s = (now-cset['source']['observed']).total_seconds()
    if observed_s < 240:
        state = 'new'
    else:
        state = 'old'
    misc['state'] = state

def cset_process_local2(args, config, db, cset, meta, info):
    '''Preprocess cset, i.e. locally compute various information based on meta, tag
       info or other data.
    '''
    cset_process_local1(args, config, db, cset, info)
    misc = info['misc']

    tagdiff = info['tagdiff']
    max_len = 20
    for action in ['create', 'modify', 'delete']:
        tdiff = []
        sorted_tags = sorted(tagdiff[action].items(), key=operator.itemgetter(1), reverse=True)
        for k,v in sorted_tags:
            tdiff.append((k, v, action))
            if len(tdiff) == max_len<len(sorted_tags): # Max tags allowed
                num = len(sorted_tags)-max_len
                misc['processed_tagdiff_'+action+'_trailer'] = '{} other {} item{}'.format(num, action, '' if num==1 else 's')
                break
        misc['processed_tagdiff_'+action] = tdiff

    unchanged_tags = info['tags']
    tagdiff = info['tagdiff']
    misc['dk_address_node_changes'] = len([d for d in unchanged_tags if d.startswith('osak:identifier')])
    def isaddr(t):
        return t.startswith('osak:identifier')
    for k in tagdiff.keys():
        misc['dk_address_node_changes'] += len(filter(isaddr, tagdiff[k]))

def cset_process_open(args, config, db, cset, debug=0):
    '''Initial processing of changesets. Also applied to open changesets'''
    info = {'state': {}}
    cset_process_local1(args, config, db, cset, info)
    return info

def cset_process(args, config, db, cset, debug=0):
    '''One-time processing of closed changesets'''
    cid = cset['cid']
    geojson = config.get('path', 'tracker')+'/'+config.get('geojsondiff-filename', 'tracker')
    bbox = config.get('path', 'tracker')+'/'+config.get('bounds-filename', 'tracker')
    truncated = None
    diffs = None
    try:
        c = OsmChangeset.Changeset(cid, api=config.get('osm_api_url','tracker'))
        c.apidebug = debug
        c.datadebug = debug
        c.downloadMeta() # FIXME: Use data from db
        c.downloadData()
        #c.downloadGeometry()
        maxtime = config.get('cset_processing_time_max_s', 'tracker')
        c.downloadHistory(maxtime=maxtime)
        #c.getReferencedElements()
        c.buildSummary(maxtime=maxtime)
        diffs = c.buildDiffList(maxtime=maxtime)
    except OsmChangeset.Timeout as e:
        truncated = 'Timeout'

    info = {'state': {},
            #'meta': c.meta,
            'summary': c.summary,
            'tags': c.tags, 'tagdiff': c.tagdiff,
            'simple_nodes': c.simple_nodes, 'diffs': diffs,
            'other_users': c.other_users, 'mileage_m': c.mileage}
    if truncated:
        info['state']['truncated'] = truncated
        logger.error('Changeset {} not fully processed: {}'.format(c.id, truncated))
    else:
        if geojson:
            fn = geojson.format(id=c.id)
            with open(fn, 'w') as f:
                json.dump(c.getGeoJsonDiff(), f)

    if bbox:
        b = '{},{},{},{}'.format(c.meta['min_lat'], c.meta['min_lon'],
                                       c.meta['max_lat'], c.meta['max_lon'])
        fn = bbox.format(id=c.id)
        with open(fn, 'w') as f:
            f.write(b)

    cset_process_local2(args, config, db, cset, c.meta, info)
    c.unload()
    return info

def cset_reprocess(args, config, db, cset):
    '''Periodic re-processing of closed changesets'''
    cid = cset['cid']
    info = db.chgset_get_info(cid)
    cset_process_local1(args, config, db, cset, info)
    return info

def diff_fetch(args, config, db, area):
    logger.debug('Fetching minutely diff')
    dapi = osmdiff.OsmDiffApi()
    if args.log_level == 'DEBUG':
        dapi.debug = True

    ptr = db.pointer

    if args.history:
        history = HumanTime.human2date(args.history)
        head = dapi.get_state('minute')
        pointer = dapi.get_seqno_le_timestamp('minute', history, head)
        db.pointer = pointer
    elif args.initptr or not ptr:
        head = dapi.get_state('minute', seqno=None)
        head.sequenceno_advance(offset=-1)
        db.pointer = head
        logger.debug('Initialized pointer to:{}'.format(db.pointer))

    while True:
        try:
            ptr = db.pointer['seqno']
            head = dapi.get_state('minute', seqno=None)
            start = None
            if ptr <= head.sequenceno:
                logger.debug('Fetching diff, ptr={}, head={}'.format(ptr, head.sequenceno))
                start = time.time()
                chgsets = fetch_and_process_diff(config, dapi, ptr, 'minute')
                logger.debug('{} changesets: {}'.format(len(chgsets), chgsets))
                for cid in chgsets:
                    source = {'type': 'minute',
                              'sequenceno': ptr,
                              'observed': datetime.datetime.utcnow().replace(tzinfo=pytz.utc)}
                    db.chgset_append(cid, source)
                # Set timestamp from old seqno as new seqno might not yet exist
                nptr = dapi.get_state('minute', seqno=db.pointer['seqno'])
                db.pointer_meta_update({'timestamp': nptr.timestamp()})
                db.pointer_advance()
        except (urllib2.HTTPError, urllib2.URLError, socket.error, socket.timeout) as e:
            logger.error('Error retrieving OSM data: '.format(e))
            logger.error(traceback.format_exc())
            time.sleep(60)

        if args.track:
            if ptr >= head.sequenceno: # No more diffs to fetch
                if start:
                    end = time.time()
                    elapsed = end-start
                    delay = min(60, max(0, 60-elapsed))
                    logger.debug('Processing seqno {} took {:.2f}s. Sleeping {:.2f}s'.format(ptr, elapsed, delay))
                else:
                    delay = 60
                time.sleep(delay)
        else:
            break
    return 0

def csets_check_bounds(args, config, db, area):
    while True:
        cset = db.chgset_start_processing(db.STATE_NEW, db.STATE_BOUNDS_CHECK)
        if not cset:
            break
        cid = cset['cid']
        logger.debug('Cset checking bounds, cid={}'.format(cid))
        try:
            c = cset_check_bounds(args, config, area, cid)
            if c:
                logger.debug('Cset {} within area'.format(cid))
                db.chgset_set_meta(cid, c.meta)
                db.chgset_processed(cset, state=db.STATE_BOUNDS_CHECKED)
            else:
                logger.debug('Cset {} not within area'.format(cid))
                db.chgset_drop(cid)
        except osmapi.ApiError as e:
            logger.error('Failed reading changeset {}: {}'.format(cid, e))
            db.chgset_processed(c, state=db.STATE_DONE, failed=True)
    return 0

def csets_analyze(args, config, db, area):
    # Initial and open changesets
    while True:
        cset = db.chgset_start_processing(db.STATE_BOUNDS_CHECKED, db.STATE_ANALYZING1)
        if not cset:
            break
        logger.debug('Cset {} analysis step 1'.format(cset['cid']))
        info = cset_process_open(args, config, db, cset)
        db.chgset_set_info(cset['cid'], info)
        meta = db.chgset_get_meta(cset['cid'])
        if meta['open']:
            db.chgset_processed(cset, state=db.STATE_OPEN, refreshed=True)
        else:
            db.chgset_processed(cset, state=db.STATE_CLOSED, refreshed=True)

    # One-time processing when changesets are closed
    while True:
        cset = db.chgset_start_processing(db.STATE_CLOSED, db.STATE_ANALYZING2)
        if not cset:
            break
        logger.debug('Cset {} analysis step 2'.format(cset['cid']))
        info = cset_process(args, config, db, cset)
        db.chgset_set_info(cset['cid'], info)
        db.chgset_processed(cset, state=db.STATE_DONE, refreshed=True)

    # Peridic reprocessing of open changesets
    now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
    dt = now-datetime.timedelta(minutes=config.get('refresh_open_minutes','tracker'))
    while True:
        cset = db.chgset_start_processing(db.STATE_OPEN, db.STATE_ANALYZING1, before=dt, timestamp='refreshed')
        if not cset:
            break
        logger.info('Reprocess OPEN changeset, cid={}'.format(cset['cid']))
        info = cset_process_open(args, config, db, cset)
        db.chgset_set_info(cset['cid'], info)
        meta = db.chgset_get_meta(cset['cid'])
        if meta['open']:
            db.chgset_processed(cset, state=db.STATE_OPEN, refreshed=True)
        else:
            db.chgset_processed(cset, state=db.STATE_CLOSED, refreshed=True)

    # Peridic reprocessing of finished changesets
    # Called functions may have longer delays on e.g. when meta is refreshed
    now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
    dt = now-datetime.timedelta(minutes=config.get('refresh_meta_minutes','tracker'))
    while True:
        cset = db.chgset_start_processing(db.STATE_DONE, db.STATE_REANALYZING, before=dt, timestamp='refreshed')
        if not cset:
            break
        info = cset_reprocess(args, config, db, cset)
        db.chgset_set_info(cset['cid'], info)
        db.chgset_processed(cset, state=db.STATE_DONE, refreshed=True)

    # Drop old changesets
    now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
    horizon_s = config.get('horizon_hours','tracker')*3600
    dt = now-datetime.timedelta(seconds=horizon_s)
    while True:
        cset = db.chgset_start_processing(db.STATE_DONE, db.STATE_REANALYZING, before=dt, timestamp='refreshed')
        if not cset:
            break
        logger.info('Dropping cset {} due to age {}s'.format(cset['cid'], age_s))
        db.chgset_drop(cset['cid'])

    return 0

def load_backend(backend, config):
    logger.debug("Loading backend {}".format(backend))
    back = importlib.import_module(backend['type'])
    back = reload(back) # In case it changed
    return back.Backend(config, backend)

def run_backends(args, config, db, area):
    blist = config.get('backends', 'tracker')
    if not blist:
        print 'No backends specified'
        return
    backends = []
    for backend in blist:
        backends.append(load_backend(backend, config))
    logger.debug('Loaded {} backends'.format(len(backends)))
    while True:
        for b in backends:
            b.print_state(db)
        if not args.track:
            break
        time.sleep(60)
    return 0

def main(argv):
    logging.config.fileConfig('logging.conf')
    parser = argparse.ArgumentParser(description='OSM Changeset diff filter')
    parser.add_argument('-l', dest='log_level', default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Set the log level')
    subparsers = parser.add_subparsers()

    parser_diff_fetch = subparsers.add_parser('diff-fetch')
    parser_diff_fetch.set_defaults(func=diff_fetch)
    parser_diff_fetch.add_argument('--initptr', action='store_true', default=False,
                                   help='Reset OSM minutely diff pointer')
    parser_diff_fetch.add_argument('-H', dest='history', help='Define how much history to fetch')
    parser_diff_fetch.add_argument('--track', action='store_true', default=False,
                                   help='Fetch current and future minutely diffs')

    parser_csets_checkbounds = subparsers.add_parser('csets-check-bounds')
    parser_csets_checkbounds.set_defaults(func=csets_check_bounds)

    parser_csets_analyze = subparsers.add_parser('csets-analyze')
    parser_csets_analyze.set_defaults(func=csets_analyze)

    parser_run_backends = subparsers.add_parser('run-backends')
    parser_run_backends.set_defaults(func=run_backends)
    parser_run_backends.add_argument('--track', action='store_true', default=False,
                                   help='Track changes and re-run backends')

    args = parser.parse_args()
    logging.getLogger('').setLevel(getattr(logging, args.log_level))

    config = configfile.Config()
    config.load()

    areafile = config.get('area-filter', 'tracker')
    if areafile:
        area = Poly.Poly()
        area.load(areafile)
        logger.debug('Loaded area polygon from \'{0}\' with {1} points.'.format(areafile, len(area)))
        logger.debug('bounds={}'.format(area.poly.bounds))

    db = database.DataBase()
    logger.debug('Connected to db: {}'.format(db))

    return args.func(args, config, db, area)

if __name__ == "__main__":
   sys.exit(main(sys.argv[1:]))
