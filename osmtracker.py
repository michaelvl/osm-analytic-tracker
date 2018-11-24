#!/usr/bin/env python

import sys, time
import argparse
import osmapi
import osm.changeset
import osm.diff as osmdiff
import osm.poly
import json, pickle
import datetime, pytz, dateutil.parser
import pprint
import logging, logging.config
import db as database
import config as configfile
import importlib
import ColourScheme as col
import HumanTime
import operator
import requests, socket
import traceback
import BackendHtml, BackendHtmlSummary, BackendGeoJson
import prometheus_client
import messagebus
import eventlet

eventlet.monkey_patch()

logger = logging.getLogger('osmtracker')

AMQP_EXCHANGE_TOPIC = 'osmtracker'     # topic
AMQP_EXCHANGE_FANOUT = 'osmtracker_bc'  # Fanout
AMQP_FILTER_QUEUE = ('new_cset', 'new_cset.osmtracker', True) # name,key,auto_delete
AMQP_ANALYSIS_QUEUE = ('analysis_cset', 'analysis_cset.osmtracker', True)
AMQP_REFRESH_QUEUE = ('refresh_cset', 'refresh_cset.osmtracker', True)
AMQP_NEW_GENERATION_KEY = 'new_generation.osmtracker'
AMQP_NEW_POINTER_KEY = 'new_replication_pointer.osmtracker'
AMQP_REPLICATION_POINTER_QUEUE = ('replication_pointer', AMQP_NEW_POINTER_KEY, True)
AMQP_QUEUES = [AMQP_FILTER_QUEUE, AMQP_ANALYSIS_QUEUE, AMQP_REFRESH_QUEUE]

EVENT_LABELS = ['event', 'action']

def fetch_and_process_diff(config, dapi, seqno, ctype):
    return dapi.get_diff_csets(seqno, ctype)

# FIXME: Refactor to use db.find with timestamps
def cset_refresh_meta(config, db, cset, no_delay=False):
    cid = cset['cid']
    logger.debug('Test refresh meta, cid {}'.format(cid))
    if no_delay or cset_ready_for_reprocessing(config, db, cid=cid):
        logger.info('Refresh meta for cid {} (no_delay={})'.format(cid, no_delay))
        c = osm.changeset.Changeset(cid, api=config.get('osm_api_url','tracker'))
        c.downloadMeta()
        updated = db.chgset_set_meta(cid, c.meta)
        db.chgset_processed(cset, state=None, refreshed=True)
        return updated
    return False

def cset_process_local1(config, db, cset, info):
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

    if cset_refresh_meta(config, db, cset, no_delay=('timestamp_type' not in misc)) or 'timestamp_type' not in misc:
        (tstype, timestamp) = osm.changeset.Changeset.get_timestamp(meta)
        ts_type2txt = { 'created_at': 'Started', 'closed_at': 'Closed' }
        misc['timestamp_type'] = tstype
        misc['timestamp_type_txt'] = ts_type2txt[tstype]
        misc['timestamp'] = timestamp
        # Update generation, notes etc might have changed
        db.generation_advance()

    now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
    observed_s = (now-cset['source']['observed']).total_seconds()
    #if observed_s < 240:
    #    state = 'new'
    #else:
    state = 'old'
    misc['state'] = state

def cset_process_local2(config, db, cset, meta, info):
    '''Preprocess cset, i.e. locally compute various information based on meta, tag
       info or other data.
    '''
    cset_process_local1(config, db, cset, info)
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
        
def cset_process_open(config, db, cset, debug=0):
    '''Initial processing of changesets. Also applied to open changesets'''
    info = {'state': {}}
    cset_process_local1(config, db, cset, info)
    return info

def cset_process(config, db, cset, debug=0):
    '''One-time processing of closed changesets'''
    cid = cset['cid']
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

    cset_process_local2(config, db, cset, c.meta, info)

    # Apply labels
    labelrules = config.get('post_labels','tracker')
    clabels = c.build_labels(labelrules)
    logger.debug('Added post labels to cid {}: {}'.format(cid, clabels))
    cset['labels'] += clabels

    c.unload()
    return info

def cset_reprocess(config, db, cset):
    '''Periodic re-processing of closed changesets'''
    cid = cset['cid']
    info = db.chgset_get_info(cid)
    cset_process_local1(config, db, cset, info)
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
                                           'Minutely diff processing time (seconds)')
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
        m_events = prometheus_client.Counter('osmtracker_events',
                                             'Number of events', EVENT_LABELS)

    dapi = osmdiff.OsmDiffApi()
    ptr = db.pointer

    if args:
        if args.log_level == 'DEBUG':
            dapi.debug = True

        amqp = messagebus.Amqp(args.amqp_url, AMQP_EXCHANGE_TOPIC, 'topic', AMQP_QUEUES)
        amqp_gen = messagebus.Amqp(args.amqp_url, AMQP_EXCHANGE_FANOUT, 'fanout', [], [])

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
                logger.debug('Fetching diff, ptr={}, head={}'.format(ptr, head))
                start = time.time()
                chgsets = fetch_and_process_diff(config, dapi, ptr, 'minute')
                logger.debug('{} changesets: {}'.format(len(chgsets), chgsets))
                for cid,cset in chgsets.iteritems():
                    msg = cset
                    msg['source']['observed'] = cset['source']['observed'].isoformat()
                    msg['points_bbox'] = cset['points_bbox'].to_dict()
                    if not msg['points_bbox']:
                        del msg['points_bbox']
                    logger.debug('Sending to messagebus: {}'.format(cset))
                    r = amqp.send(cset, schema_name='cset', schema_version=1,
                              routing_key='new_cset.osmtracker')
                    logger.debug('Send result: {}'.format(r))
                    m_events.labels('filter', 'in').inc()
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
                msg = {'pointer': seqno}
                r = amqp_gen.send(msg, schema_name='replication_pointer', schema_version=1,
                                  routing_key=AMQP_NEW_POINTER_KEY)
                logger.debug('New pointer send result: {}'.format(r))
                m_events.labels('new_pointer', 'in').inc()
        except KeyboardInterrupt as e:
            logger.warn('Processing interrupted, exiting...')
            raise e
        except (requests.exceptions.Timeout, requests.exceptions.HTTPError, socket.error, socket.timeout, eventlet.timeout.Timeout) as e:
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

def cset_filter(config, db, new_cset):
        cid = new_cset['cid']

        # Apply labels
        labelrules = config.get('pre_labels','tracker')
        try:
            with eventlet.Timeout(10):
                start = time.time()
                logger.debug('Downloading cset {}'.format(cid))
                c = osm.changeset.Changeset(cid, api=config.get('osm_api_url','tracker'))
                logger.debug('Downloading meta for cset {}'.format(cid))
                c.downloadMeta()
                logger.debug('Downloading took {:.2f}s'.format(time.time()-start))
                clabels = c.build_labels(labelrules)
                logger.debug('Added labels to cid {}: {}'.format(cid, clabels))
        except (osmapi.ApiError, eventlet.timeout.Timeout) as e:
            logger.error('Failed reading changeset {}: {}'.format(cid, e))
            #db.chgset_processed(cset, state=db.STATE_QUARANTINED, failed=True)
            return False

        # Check labels
        labelfilters = config.get('prefilter_labels','tracker')
        passed_filters = False
        for lf in labelfilters:
            logger.debug('lf={}'.format(lf))
            if set(lf).issubset(set(clabels)):
                logger.debug("Cset labels '{}' is subset of '{}'".format(clabels, lf))
                passed_filters = True

        if not passed_filters:
            logger.debug('Cset {} does not match filters'.format(cid))
        else:
            logger.debug('Cset {} matches filters'.format(cid))
            source = { 'type': new_cset['source']['type'],
                       'sequenceno': new_cset['source']['sequenceno'],
                       'observed': dateutil.parser.parse(new_cset['source']['observed'])}
            cset = db.chgset_append(cid, source)
            cset['labels'] = clabels
            db.chgset_set_meta(cid, c.meta)
            db.chgset_processed(cset, state=db.STATE_BOUNDS_CHECKED)
            return True
        return False

def csets_filter_worker(args, config, db):

    class FilterAmqp(messagebus.Amqp):
        def on_message(self, payload, message):
            logger.info('Filter: {}'.format(payload))
            start = time.time()
            if cset_filter(self.config, self.db, payload):
                amqp.send(payload, schema_name='cset', schema_version=1,
                          routing_key='analysis_cset.osmtracker')
                m_events.labels('analysis', 'in').inc()
            m_events.labels('filter', 'out').inc()
            elapsed = time.time()-start
            m_filter_time.observe(elapsed)
            logger.info('Filtering of cid {} took {:.2f}s'.format(payload['cid'], elapsed))
            message.ack()

    amqp = FilterAmqp(args.amqp_url, AMQP_EXCHANGE_TOPIC, 'topic', AMQP_QUEUES, [AMQP_FILTER_QUEUE])
    amqp.config = config
    amqp.db = db

    if args.metrics:
        m_events = prometheus_client.Counter('osmtracker_events',
                                             'Number of events', EVENT_LABELS)
        m_filter_time = prometheus_client.Histogram('osmtracker_changeset_filter_processing_time_seconds',
                                                    'Changeset filtering time (seconds)')

    logger.debug('Starting filter worker')
    amqp.run()

def csets_analyse_initial(config, db, new_cset=None):
    # Initial and open changesets
    while True:
        try:
            if new_cset:
                cid = new_cset['cid']
            else:
                cid = None
            cset = db.chgset_start_processing([db.STATE_BOUNDS_CHECKED,db.STATE_OPEN,db.STATE_ANALYSING2], db.STATE_ANALYSING1, cid=cid)
            if not cset:
                logger.warning('Could not find cid {}'.format(cid))
                return False
            logger.debug('Cset {} analysis step 1'.format(cid))
            info = cset_process_open(config, db, cset)
            db.chgset_set_info(cid, info)
            meta = db.chgset_get_meta(cset['cid'])
            logger.info('Cset {} meta={}'.format(cid, meta))
            if meta['open']:
                logger.debug('Cset {} is open, stopping analysis'.format(cid))
                logger.info('Cset {} is open, stopping analysis: meta={}'.format(cid, meta))
                db.chgset_processed(cset, state=db.STATE_OPEN, refreshed=True)
                return False
            else:
                db.chgset_processed(cset, state=db.STATE_CLOSED, refreshed=True)  # FIXME
                csets_analyse_on_close(config, db, new_cset)
                return True
        except KeyboardInterrupt as e:
            logging.warn('Processing interrupted, restoring cid {} state to BOUNDS_CHECKED...'.format(cset['cid']))
            db.chgset_processed(cset, state=db.STATE_BOUNDS_CHECKED)
            raise e
        if new_cset:
            break
    return False

def csets_analyse_on_close(config, db, new_cset=None):
    # One-time processing when changesets are closed
    while True:
        if new_cset:
            cid = new_cset['cid']
        else:
            cid = None
        cset = db.chgset_start_processing(db.STATE_CLOSED, db.STATE_ANALYSING2, cid=cid)
        if not cset:
            break
        try:
            logger.debug('Cset {} analysis step 2'.format(cset['cid']))
            info = cset_process(config, db, cset)
            db.chgset_set_info(cset['cid'], info)
            meta = db.chgset_get_meta(cset['cid'])
            db.chgset_processed(cset, state=db.STATE_DONE, refreshed=True)
        except KeyboardInterrupt as e:
            logging.warn('Processing interrupted, restoring cid {} state to CLOSED...'.format(cset['cid']))
            db.chgset_processed(cset, state=db.STATE_CLOSED)
            raise e
        if new_cset:
            break

def cset2csetmsg(cset):
    c = {'cid': cset['cid'], 'source': cset['source'] }
    c['source']['observed'] = cset['source']['observed'].isoformat()
    return c

def cset_check_reprocess_open(amqp, config, db, cset):
    now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
    dt = now-datetime.timedelta(minutes=config.get('refresh_open_minutes','tracker'))
    if cset['refreshed']<dt:
        logger.info('Request refresh of OPEN cset {}'.format(cset['cid']))
        amqp.send(cset2csetmsg(cset), schema_name='cset', schema_version=1,
                  routing_key='analysis_cset.osmtracker')
        return True
    return False

def cset_ready_for_reprocessing(config, db, cset=None, cid=None):
    if not cset:
        cset = db.chgset_get(cid)
        if not cset:
            return True
    refresh_period = config.get('refresh_meta_minutes','tracker')
    if refresh_period>0:
        now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
        dt = now-datetime.timedelta(minutes=refresh_period)
        if cset['refreshed']<dt:
            logger.debug('Cset {} ready for refresh, refreshed {}'.format(cset['cid'], HumanTime.date2human(dt)))
            return True
    logger.debug('Cset {} not ready for refresh, refreshed {}'.format(cset['cid'], cset['refreshed']))
    return False

def cset_check_reprocess_done(config, db, cset):
    # Peridic reprocessing of finished changesets
    # Called functions may have longer delays on e.g. when meta is refreshed
    if cset_ready_for_reprocessing(config, db, cset=cset):
        logger.info('Request refresh of cset {}'.format(cset['cid']))
        return True
    return False

# def csets_analyse_drop_old(args, config, db):
#     # Drop old changesets
#     now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
#     horizon_s = config.get('horizon_hours','tracker')*3600
#     dt = now-datetime.timedelta(seconds=horizon_s)
#     while True:
#         cset = db.chgset_start_processing([db.STATE_DONE, db.STATE_QUARANTINED], db.STATE_REANALYSING, before=dt, timestamp='updated')
#         if not cset:
#             break
#         logger.info('Dropping cset {} due to age'.format(cset['cid']))
#         db.chgset_drop(cset['cid'])

#     return 0
def cset_check_drop_old(config, db, cset=None, cid=None):
    if not cset:
        cset = db.chgset_get(cid)
        if not cset:
            return True
    horizon_s = config.get('horizon_hours','tracker')*3600
    if horizon_s>0:
        now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
        dt = now-datetime.timedelta(seconds=horizon_s)
        if cset['updated']<dt:
            logger.info('Cset {} ready to be dropped, updated {}'.format(cset['cid'], HumanTime.date2human(dt)))
            return True
    logger.debug('Cset {} not ready to be dropped, updated {}'.format(cset['cid'], cset['updated']))
    return False

def load_backend(backend, config):
    logger.debug("Loading backend {}".format(backend))
    return globals()[backend['type']].Backend(config, backend)

def run_backends(args, config, db, key):
    blist = config.get('backends')
    if not blist:
        logger.warning('No backends specified')
        return
    backends = []
    for backend in blist:
        backends.append(load_backend(backend, config))
    logger.debug('Loaded {} backends'.format(len(backends)))

    for b in backends:
        starttime = time.time()
        b.print_state(db, key)
        logger.info('Running backend {} took {:.2f}s'.format(b, time.time()-starttime))

def backends_worker(args, config, db):

    class BackendAmqp(messagebus.Amqp):
        def on_message(self, payload, message):
            key = message.delivery_info['routing_key']
            logger.info('Run backends, key: {}'.format(key))
            if key==AMQP_NEW_GENERATION_KEY:
                m_events.labels('new_generation', 'out').inc()
            elif key==AMQP_NEW_POINTER_KEY:
                m_events.labels('new_pointer', 'out').inc()
            else:
                logger.error('Unknown key {}'.format(key))
            start = time.time()
            run_backends(args, config, db, key)
            elapsed = time.time()-start
            logger.info('Running all backends (key {}) took {:.2f}s'.format(key, elapsed))
            m_backend_time.observe(elapsed)
            message.ack()

    # Will create initial versions
    run_backends(args, config, db, AMQP_NEW_GENERATION_KEY)

    queue = [(socket.gethostname(), '', True)] # No needed on broadcast exchange
    amqp = BackendAmqp(args.amqp_url, AMQP_EXCHANGE_FANOUT, 'fanout', queue, queue)
    amqp.config = config
    amqp.db = db

    if args.metrics:
        m_backend_time = prometheus_client.Histogram('osmtracker_backend_processing_time_seconds',
                                                     'Backend refresh time (seconds)',
                                                     buckets=(.1, .5, 1.0, 2.5, 5.0, 7.5, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0, 55.0, 60.0, 80.0, 100.0, 130.0, 160.0, float("inf")))
        m_events = prometheus_client.Counter('osmtracker_events',
                                             'Number of events', EVENT_LABELS)

    logger.debug('Starting backend worker, queue/routing-key: {}'.format(queue))
    amqp.run()

def csets_analysis_worker(args, config, db):

    class AnalysisAmqp(messagebus.Amqp):
        def on_message(self, payload, message):
            key = message.delivery_info['routing_key']
            logger.info('Analyse: {}, key: {}'.format(payload, key))
            start = time.time()
            try:
                with eventlet.Timeout(config.get('cset_processing_time_max_s', 'tracker')):
                    if key=='analysis_cset.osmtracker':
                        post_new_generation = csets_analyse_initial(self.config, self.db, payload)
                        if post_new_generation:
                            gen = db.generation_advance()
                            msg = {'generation': gen}
                            amqp_gen.send(msg, schema_name='generation', schema_version=1,
                                          routing_key=AMQP_NEW_GENERATION_KEY)
                            m_events.labels('new_generation', 'in').inc()
                        elapsed = time.time()-start
                        m_events.labels('analysis', 'out').inc()
                        m_analysis_time.observe(elapsed)
                    elif key=='refresh_cset.osmtracker':
                        cset_refresh_meta(self.config, self.db, payload)
                        m_events.labels('refresh', 'out').inc()
                        elapsed = time.time()-start
                        m_refresh_time.observe(elapsed)
                    logger.info('Analysis of cid {} took {:.2f}s'.format(payload['cid'], elapsed))
            except eventlet.timeout.Timeout as e:
                logger.error('Failed analysing changeset {}: {}'.format(payload['cid'], e))
            message.ack()

    queues = [AMQP_ANALYSIS_QUEUE, AMQP_REFRESH_QUEUE]
    amqp_gen = messagebus.Amqp(args.amqp_url, AMQP_EXCHANGE_FANOUT, 'fanout', [], [])
    amqp = AnalysisAmqp(args.amqp_url, AMQP_EXCHANGE_TOPIC, 'topic', AMQP_QUEUES, queues)
    amqp.config = config
    amqp.db = db

    if args.metrics:
        m_events = prometheus_client.Counter('osmtracker_events',
                                             'Number of events', EVENT_LABELS)
        m_analysis_time = prometheus_client.Histogram('osmtracker_changeset_analysis_processing_time_seconds',
                                                      'Changeset analysis time (seconds)',
                                                      buckets=(.1, .5, 1.0, 2.5, 5.0, 7.5, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0, 55.0, 60.0, 80.0, 100.0, 130.0, 160.0, float("inf")))
        m_refresh_time = prometheus_client.Histogram('osmtracker_changeset_refresh_processing_time_seconds',
                                                     'Changeset refresh time (seconds)')

    logger.debug('Starting analysis worker, queue/routing-key: {}'.format(queues))
    amqp.run()

def supervisor(args, config, db):
    if args.metrics:
        m_events = prometheus_client.Counter('osmtracker_events',
                                             'Number of events', EVENT_LABELS)
        m_changesets = prometheus_client.Gauge('osmtracker_changeset_cnt',
                                               'Number of changesets in database',
                                               ['state'])

    amqp = messagebus.Amqp(args.amqp_url, AMQP_EXCHANGE_TOPIC, 'topic', AMQP_QUEUES, [])

    while True:
        logger.debug('Starting supervision loop')
        new_generation = False
        horizon_s = config.get('horizon_hours','tracker')*3600
        start = time.time()
        cset_cnt = {}
        for state in db.all_states:
            cset_cnt[state] = 0
        to_drop = []
        for c in db.chgsets_find(state=None):
            if 'cid' not in c.keys():
                logger.error('cid not in changeset, dropping. Keys:{}'.format(c.keys()))
                to_drop.append(c['_id'])
            else:
                logger.debug('Found cid {}, state:{}, refreshed:{}'.format(c['cid'], c['state'], c['refreshed']))
                if cset_check_drop_old(config, db, cid=c['cid']):
                    to_drop.append(c['cid'])
                else:
                    if args.metrics:
                        cset_cnt[c['state']] += 1
                    if c['state']==db.STATE_OPEN:
                        if cset_check_reprocess_open(amqp, config, db, c):
                            m_events.labels('analysis', 'in').inc()
                    elif c['state']==db.STATE_DONE:
                        if cset_check_reprocess_done(config, db, c):
                            amqp.send(cset2csetmsg(c), schema_name='cset', schema_version=1,
                                      routing_key='refresh_cset.osmtracker')
                            m_events.labels('refresh', 'in').inc()
                    elif c['state']==db.STATE_ANALYSING2:
                        if cset_check_reprocess_done(config, db, c):
                            #amqp.send(cset2csetmsg(c), schema_name='cset', schema_version=1,
                            #          routing_key='analysis_cset.osmtracker')
                            #m_events.labels('analysis', 'in').inc()
                            logging.error('Dropping reprocess-ready changeset from state ANALYSING2')
                            to_drop.append(c['cid'])
        if args.metrics:
            for state in db.all_states:
                m_changesets.labels(state=state).set(cset_cnt[state])
        for cid in to_drop:
            logger.info('Dropping cid {}'.format(cid))
            db.chgset_drop(cid)
            # FIXME
        if not args.track:
            break
        logger.info('Supervision loop took {:.2f}s. State stats: {}'.format(time.time()-start, cset_cnt))
        time.sleep(60)

def main():
    logging.config.fileConfig('logging.conf')
    parser = argparse.ArgumentParser(description='OSM Changeset diff filter')
    parser.add_argument('-l', dest='log_level', default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Set the log level')
    parser.add_argument('--configfile', dest='configfile', default='./config.json',
                        help='Set config file')
    parser.add_argument('--db', dest='db_url', default='mongodb://localhost:27017/',
                        help='Set url for database')
    parser.add_argument('--metrics', dest='metrics', action='store_true', default=False,
                        help='Enable metrics through Prometheus client API')
    parser.add_argument('--metricsport', dest='metricsport', type=int, default=8000,
                        help='Port through which to serve metrics')
    parser.add_argument('--amqp', dest='amqp_url', default='',
                        help='Set url for message bus')
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
    parser_csets_filter.set_defaults(func=csets_filter_worker)

    parser_csets_analyse = subparsers.add_parser('csets-analyse')
    parser_csets_analyse.set_defaults(func=csets_analysis_worker)

    parser_run_backends = subparsers.add_parser('run-backends')
    parser_run_backends.set_defaults(func=backends_worker)

    parser_supervisor = subparsers.add_parser('supervisor')
    parser_supervisor.set_defaults(func=supervisor)
    parser_supervisor.add_argument('--track', action='store_true', default=False,
                                   help='Track changes and re-run supervisor tasks periodically')

    args = parser.parse_args()
    logging.getLogger('').setLevel(getattr(logging, args.log_level))

    config = configfile.Config()
    config.load(file=args.configfile)

    if args.metrics:
        prometheus_client.start_http_server(args.metricsport)

    if args.func==diff_fetch:
        dbadm=True
    else:
        dbadm=False
    db = database.DataBase(url=args.db_url, admin=dbadm)
    logger.info('DB URL: {} (RW={})'.format(db, dbadm))

    if args.amqp_url!='':
        logger.info('AMQP URL {}, exchange {}'.format(args.amqp_url, AMQP_EXCHANGE_TOPIC))

    return args.func(args, config, db)

if __name__ == "__main__":
   sys.exit(main())
