#!/usr/bin/env python

import sys, time
import argparse
import osmapi
import osm.changeset
import osm.diff as osmdiff
import osm.poly
import json, pickle
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
import BackendHtml, BackendHtmlSummary, BackendGeoJson
import prometheus_client

logger = logging.getLogger('osmtracker')

def fetch_and_process_diff(config, dapi, seqno, ctype):
    chgsets = dapi.get_diff_csets(seqno, ctype)
    return chgsets

# FIXME: Refactor to use db.find with timestamps
def cset_refresh_meta(args, config, db, cset, no_delay=False):
    cid = cset['cid']
    timeout_s = config.get('refresh_meta_minutes', 'tracker')*60
    refresh = no_delay
    if timeout_s>0:
       now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
       last_refresh = cset['refreshed']
       age_s = (now-last_refresh).total_seconds()
       if age_s > timeout_s:
           logger.debug('Refresh meta due to age {}s, timeout {}s'.format(age_s, timeout_s))
           refresh = True
    if refresh:
        logger.info('Refresh meta for cid {} (no_delay={})'.format(cid, no_delay))
        c = osm.changeset.Changeset(cid, api=config.get('osm_api_url','tracker'))
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
    if not meta:
        logger.error('No meta for cset:{}'.format(cset))

    if not 'misc' in info:
        misc = {}
        info['misc'] = misc
        user = meta['user']
        colours = col.ColourScheme(seed=0)
        misc['user_colour'] = colours.get_colour(user)
    else:
        misc = info['misc']

    if cset_refresh_meta(args, config, db, cset, no_delay=('timestamp_type' not in misc)) or 'timestamp_type' not in misc:
        (tstype, timestamp) = osm.changeset.Changeset.get_timestamp(meta)
        ts_type2txt = { 'created_at': 'Started', 'closed_at': 'Closed' }
        misc['timestamp_type'] = tstype
        misc['timestamp_type_txt'] = ts_type2txt[tstype]
        misc['timestamp'] = timestamp
        # Update generation, notes etc might have changed
        db.generation_advance()

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
        
def cset_process_open(args, config, db, cset, debug=0):
    '''Initial processing of changesets. Also applied to open changesets'''
    info = {'state': {}}
    cset_process_local1(args, config, db, cset, info)
    return info

def cset_process(args, config, db, cset, debug=0):
    '''One-time processing of closed changesets'''
    cid = cset['cid']
    ######geojson = config.get('path', 'tracker')+'/'+config.get('geojsondiff-filename', 'tracker')
    ####bbox = config.get('path', 'tracker')+'/'+config.get('bounds-filename', 'tracker')
    truncated = None
    diffs = None
    try:
        c = osm.changeset.Changeset(cid, api=config.get('osm_api_url','tracker'))
        c.apidebug = debug
        c.datadebug = debug
        c.downloadMeta() # FIXME: Use data from db
        c.downloadData()
        #c.downloadGeometry()
        maxtime = config.get('cset_processing_time_max_s', 'tracker')
        c.downloadGeometry(maxtime=maxtime)
        c.getGeoJsonDiff()
        #c.getReferencedElements()
        c.buildSummary(maxtime=maxtime)
        c.buildDiffList(maxtime=maxtime)
    except osm.changeset.Timeout as e:
        truncated = 'Timeout'

    info = c.data_export()

    if truncated:
        info['state']['truncated'] = truncated
        logger.error('Changeset {} not fully processed: {}'.format(c.id, truncated))
    # else:
    #     if geojson:
    #         fn = geojson.format(id=c.id)
    #         with open(fn, 'w') as f:
    #             json.dump(c.getGeoJsonDiff(), f)

    # if bbox:
    #     b = '{},{},{},{}'.format(c.meta['min_lat'], c.meta['min_lon'],
    #                                    c.meta['max_lat'], c.meta['max_lon'])
    #     fn = bbox.format(id=c.id)
    #     with open(fn, 'w') as f:
    #         f.write(b)

    cset_process_local2(args, config, db, cset, c.meta, info)

    # Apply labels
    labelrules = config.get('post_labels','tracker')
    clabels = c.build_labels(labelrules)
    logger.debug('Added post labels to cid {}: {}'.format(cid, clabels))
    cset['labels'] += clabels

    c.unload()
    return info

def cset_reprocess(args, config, db, cset):
    '''Periodic re-processing of closed changesets'''
    cid = cset['cid']
    info = db.chgset_get_info(cid)
    cset_process_local1(args, config, db, cset, info)
    return info

def diff_fetch(args, config, db):
    logger.debug('Fetching minutely diff')

    if args and args.simulate:
        cid = args.simulate
        source = {'type': 'minute',
                  'sequenceno': 123456789,
                  'observed': datetime.datetime.utcnow().replace(tzinfo=pytz.utc)}
        db.chgset_append(cid, source)
        return
    if args and args.metrics:
        m_pt = prometheus_client.Histogram('osmtracker_minutely_diff_processing_time_seconds',
                                           'Processing time for latest minutely diff (seconds)')
        m_diff_ts = prometheus_client.Gauge('osmtracker_minutely_diff_timestamp',
                                            'Timestamp of recently processed minutely diff')
        m_diff_proc_ts = prometheus_client.Gauge('osmtracker_minutely_diff_processing_timestamp',
                                                 'Timestamp of when recently processed minutely diff was processed')
        m_seqno = prometheus_client.Gauge('osmtracker_minutely_diff_latest_seqno',
                                          'Sequence number of recently processed minutely diff')
        m_head_seqno = prometheus_client.Gauge('osmtracker_minutely_diff_head_seqno',
                                          'Head sequence number of minutely diff replication')
        m_csets = prometheus_client.Gauge('osmtracker_minutely_diff_csets_observed',
                                          'Number of changesets observed in recently processed minutely diff')

    dapi = osmdiff.OsmDiffApi()
    ptr = db.pointer

    if args:
        if args.log_level == 'DEBUG':
            dapi.debug = True

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
            now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
            if ptr <= head.sequenceno:
                logger.debug('Fetching diff, ptr={}, head={}'.format(ptr, head.sequenceno))
                start = time.time()
                chgsets = fetch_and_process_diff(config, dapi, ptr, 'minute')
                logger.debug('{} changesets: {}'.format(len(chgsets), chgsets))
                for cid in chgsets:
                    source = {'type': 'minute',
                              'sequenceno': ptr,
                              'observed': now}
                    db.chgset_append(cid, source)
                # Set timestamp from old seqno as new seqno might not yet exist
                seqno = db.pointer['seqno']
                nptr = dapi.get_state('minute', seqno=seqno)
                db.pointer_meta_update({'timestamp': nptr.timestamp()})
                db.pointer_advance()
                m_diff_ts.set(time.mktime(nptr.timestamp().timetuple())+nptr.timestamp().microsecond/1E6)
                m_diff_proc_ts.set_to_current_time()
                m_seqno.set(seqno)
                m_head_seqno.set(head.sequenceno)
                m_csets.set(len(chgsets))
        except KeyboardInterrupt as e:
            logger.warn('Processing interrupted, exiting...')
            raise e
        except (urllib2.HTTPError, urllib2.URLError, socket.error, socket.timeout) as e:
            logger.error('Error retrieving OSM data: '.format(e))
            logger.error(traceback.format_exc())
            time.sleep(60)

        if args and args.track:
            if start:
                end = time.time()
                elapsed = end-start
            else:
                elapsed = 0
            if args.metrics:
                m_pt.observe(elapsed)
            if ptr >= head.sequenceno: # No more diffs to fetch
                delay = min(60, max(0, 60-elapsed))
                logger.info('Processing seqno {} took {:.2f}s. Sleeping {:.2f}s'.format(ptr, elapsed, delay))
                time.sleep(delay)
            else:
                logger.info('Processing seqno {} took {:.2f}s. Head ptr is {}'.format(ptr, elapsed, head.sequenceno))
        else:
            break
    return 0

def csets_filter(args, config, db):
    while True:
        cset = db.chgset_start_processing(db.STATE_NEW, db.STATE_BOUNDS_CHECK)
        if not cset:
            break

        try:
            cid = cset['cid']

            # Apply labels
            labelrules = config.get('pre_labels','tracker')
            try:
                c = osm.changeset.Changeset(cid, api=config.get('osm_api_url','tracker'))
                c.downloadMeta()
                clabels = c.build_labels(labelrules)
                logger.debug('Added labels to cid {}: {}'.format(cid, clabels))
                cset['labels'] = clabels
            except osmapi.ApiError as e:
                logger.error('Failed reading changeset {}: {}'.format(cid, e))
                db.chgset_processed(cset, state=db.STATE_QUARANTINED, failed=True)

            # Check labels
            labelfilters = config.get('prefilter_labels','tracker')
            passed_filters = False
            for lf in labelfilters:
                logger.debug('lf={}'.format(lf))
                if set(lf).issubset(set(clabels)):
                    logger.debug("Cset labels '{}' is subset of '{}'".format(clabels, lf))
                    passed_filters = True

            if not passed_filters:
                logger.debug('Cset {} not within area'.format(cid))
                db.chgset_drop(cid)
            else:
                logger.debug('Cset {} passed filters'.format(cid))
                db.chgset_set_meta(cid, c.meta)
                db.chgset_processed(cset, state=db.STATE_BOUNDS_CHECKED)
        except KeyboardInterrupt as e:
            logging.warn('Processing interrupted, restoring cid {} state to NEW...'.format(cid))
            db.chgset_processed(cset, state=db.STATE_NEW)
            raise e
    return 0

def csets_analyze_initial(args, config, db):
    # Initial and open changesets
    while True:
        cset = db.chgset_start_processing(db.STATE_BOUNDS_CHECKED, db.STATE_ANALYZING1)
        if not cset:
            break
        try:
            logger.debug('Cset {} analysis step 1'.format(cset['cid']))
            info = cset_process_open(args, config, db, cset)
            db.chgset_set_info(cset['cid'], info)
            meta = db.chgset_get_meta(cset['cid'])
            if meta['open']:
                db.chgset_processed(cset, state=db.STATE_OPEN, refreshed=True)
            else:
                db.chgset_processed(cset, state=db.STATE_CLOSED, refreshed=True)
        except KeyboardInterrupt as e:
            logging.warn('Processing interrupted, restoring cid {} state to BOUNDS_CHECKED...'.format(cset['cid']))
            db.chgset_processed(cset, state=db.STATE_BOUNDS_CHECKED)
            raise e

def csets_analyze_on_close(args, config, db):
    # One-time processing when changesets are closed
    while True:
        cset = db.chgset_start_processing(db.STATE_CLOSED, db.STATE_ANALYZING2)
        if not cset:
            break
        try:
            logger.debug('Cset {} analysis step 2'.format(cset['cid']))
            info = cset_process(args, config, db, cset)
            db.chgset_set_info(cset['cid'], info)
            meta = db.chgset_get_meta(cset['cid'])
            db.chgset_processed(cset, state=db.STATE_DONE, refreshed=True)
        except KeyboardInterrupt as e:
            logging.warn('Processing interrupted, restoring cid {} state to CLOSED...'.format(cset['cid']))
            db.chgset_processed(cset, state=db.STATE_CLOSED)
            raise e

def csets_analyze_periodic_reprocess_open(args, config, db):
    # Peridic reprocessing of open changesets
    now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
    dt = now-datetime.timedelta(minutes=config.get('refresh_open_minutes','tracker'))
    while True:
        cset = db.chgset_start_processing(db.STATE_OPEN, db.STATE_ANALYZING1, before=dt, timestamp='refreshed')
        if not cset:
            break
        try:
            logger.info('Reprocess OPEN changeset, cid={}'.format(cset['cid']))
            info = cset_process_open(args, config, db, cset)
            db.chgset_set_info(cset['cid'], info)
            meta = db.chgset_get_meta(cset['cid'])
            if meta['open']:
                db.chgset_processed(cset, state=db.STATE_OPEN, refreshed=True)
            else:
                db.chgset_processed(cset, state=db.STATE_CLOSED, refreshed=True)
        except KeyboardInterrupt as e:
            logging.warn('Processing interrupted, restoring cid {} state to OPEN...'.format(cset['cid']))
            db.chgset_processed(cset, state=db.STATE_OPEN)
            raise e

def csets_analyze_periodic_reprocess_closed(args, config, db):
    # Peridic reprocessing of finished changesets
    # Called functions may have longer delays on e.g. when meta is refreshed
    now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
    dt = now-datetime.timedelta(minutes=config.get('refresh_meta_minutes','tracker'))
    while True:
        cset = db.chgset_start_processing(db.STATE_DONE, db.STATE_REANALYZING, before=dt, timestamp='refreshed')
        if not cset:
            break
        try:
            info = cset_reprocess(args, config, db, cset)
            db.chgset_set_info(cset['cid'], info)
            meta = db.chgset_get_meta(cset['cid'])
            db.chgset_processed(cset, state=db.STATE_DONE, refreshed=True)
        except KeyboardInterrupt as e:
            logging.warn('Processing interrupted, restoring cid {} state to DONE...'.format(cset['cid']))
            db.chgset_processed(cset, state=db.STATE_DONE)
            raise e

def csets_analyze_drop_old(args, config, db):
    # Drop old changesets
    now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
    horizon_s = config.get('horizon_hours','tracker')*3600
    dt = now-datetime.timedelta(seconds=horizon_s)
    while True:
        cset = db.chgset_start_processing([db.STATE_DONE, db.STATE_QUARANTINED], db.STATE_REANALYZING, before=dt, timestamp='updated')
        if not cset:
            break
        logger.info('Dropping cset {} due to age'.format(cset['cid']))
        db.chgset_drop(cset['cid'])

    return 0

def csets_analyze(args, config, db):
    csets_analyze_initial(args, config, db)
    csets_analyze_on_close(args, config, db)
    csets_analyze_periodic_reprocess_open(args, config, db)
    csets_analyze_periodic_reprocess_closed(args, config, db)
    csets_analyze_drop_old(args, config, db)

def load_backend(backend, config):
    logger.debug("Loading backend {}".format(backend))
    return globals()[backend['type']].Backend(config, backend)

def run_backends(args, config, db):
    blist = config.get('backends')
    if not blist:
        logger.warning('No backends specified')
        return
    backends = []
    for backend in blist:
        backends.append(load_backend(backend, config))
    logger.debug('Loaded {} backends'.format(len(backends)))
    while True:
        for b in backends:
            starttime = time.clock()
            b.print_state(db)
            logger.info('Running backend {} took {:.2f}s'.format(b, time.clock()-starttime))
        if not (args and args.track):
            break
        time.sleep(60)
    return 0

def worker(args, config, db):
    while True:
        csets_filter(args, config, db)
        csets_analyze(args, config, db)
        if not args or not args.track:
            break
        time.sleep(15)

def supervisor(args, config, db):
    if args and args.metrics:
        m_changesets = prometheus_client.Gauge('osmtracker_changeset_cnt',
                                               'Number of changesets in database',
                                               ['state'])
    while True:
        if args and args.metrics:
            cset_cnt = dict()
            for state in db.all_states:
                cset_cnt[state] = 0
            for c in db.chgsets_find():
                cid = c['cid']
                info = db.chgset_get_info(cid)
                cset_cnt[info['state']] += 1
            for state in db.all_states:
                m_changesets.labels(state=state).set(cset_cnt[state])
            if args:
                db.reanalyze(args)
        if not args or not args.track:
            break
        time.sleep(60)

def main():
    logging.config.fileConfig('logging.conf')
    parser = argparse.ArgumentParser(description='OSM Changeset diff filter')
    parser.add_argument('-l', dest='log_level', default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Set the log level')
    parser.add_argument('--configdir', dest='configdir', default='.',
                        help='Set path to config file')
    parser.add_argument('--db', dest='db_url', default='mongodb://localhost:27017/',
                        help='Set url for database')
    parser.add_argument('--metrics', dest='metrics', action='store_true', default=False,
                        help='Enable metrics through Prometheus client API')
    parser.add_argument('--metricsport', dest='metricsport', default=8000,
                        help='Port through which to serve metrics')
    subparsers = parser.add_subparsers()

    parser_diff_fetch = subparsers.add_parser('diff-fetch')
    parser_diff_fetch.set_defaults(func=diff_fetch)
    parser_diff_fetch.add_argument('--initptr', action='store_true', default=False,
                                   help='Reset OSM minutely diff pointer')
    parser_diff_fetch.add_argument('-H', dest='history', help='Define how much history to fetch')
    parser_diff_fetch.add_argument('--track', action='store_true', default=False,
                                   help='Fetch current and future minutely diffs')
    parser_diff_fetch.add_argument('--simulate', type=int, default=None, help='Simulate changeset observation')

    parser_csets_filter = subparsers.add_parser('csets-filter')
    parser_csets_filter.set_defaults(func=csets_filter)

    parser_csets_analyze = subparsers.add_parser('csets-analyze')
    parser_csets_analyze.set_defaults(func=csets_analyze)

    parser_run_backends = subparsers.add_parser('run-backends')
    parser_run_backends.set_defaults(func=run_backends)
    parser_run_backends.add_argument('--track', action='store_true', default=False,
                                   help='Track changes and re-run backends periodically')

    parser_worker = subparsers.add_parser('worker')
    parser_worker.set_defaults(func=worker)
    parser_worker.add_argument('--track', action='store_true', default=False,
                               help='Track changes and re-run worker tasks periodically')

    parser_supervisor = subparsers.add_parser('supervisor')
    parser_supervisor.set_defaults(func=supervisor)
    parser_supervisor.add_argument('--track', action='store_true', default=False,
                                   help='Track changes and re-run supervisor tasks periodically')

    args = parser.parse_args()
    logging.getLogger('').setLevel(getattr(logging, args.log_level))

    config = configfile.Config()
    config.load(path=args.configdir)

    if args.metrics:
        prometheus_client.start_http_server(args.metricsport)

    if args.func==diff_fetch:
        dbadm=True
    else:
        dbadm=False
    db = database.DataBase(url=args.db_url, admin=dbadm)
    logger.debug('Connected to db: {} (RW={})'.format(db, dbadm))

    return args.func(args, config, db)

if __name__ == "__main__":
   sys.exit(main())
