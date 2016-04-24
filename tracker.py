#!/usr/bin/python

import osmapi
import OsmDiff as osmdiff
import OsmChangeset as oc
import ColourScheme as col
import HumanTime
import pprint
import os, time, re, sys, signal
import datetime, pytz
import resource
import subprocess
import json, pickle
import importlib
import multiprocessing as mp
import logging
import urllib2
import traceback
import argparse
import config
import jinja2
import operator

logger = logging.getLogger(__name__)

class TrackedState:
    def __init__(self):
        self.clear_csets()
        self.new_generation()
        self.backends = []
        self.backend_list = []
        self.metrics = {'bytes_in': 0}
        self.last_cset_meta_refresh = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
        self.colours = col.ColourScheme()

    def clear_csets(self):
        self.chgsets = []
        self.area_chgsets = []
        self.err_chgsets = []
        self.area_chgsets_info = {}
        self.chgsets_new = []
        self.new_generation()

    def sort_csets(self):
        chginfo = self.area_chgsets_info
        self.area_chgsets.sort(key=lambda c: oc.Changeset.get_timestamp(chginfo[c]['meta'])[1])

    def close_open_cset(self):
        # Go through changesset and if anyone is marked as open, update state
        for cset_id in self.area_chgsets:
            if self.area_chgsets_info[cset_id]['meta']['open'] == 'true':
                logger.debug('Check open cset {}, current state:{}'.format(cset_id, self.area_chgsets_info[cset_id]))
                self.refresh_cset_meta(cset_id)

    def try_refresh_meta(self):
        '''Refresh meta information - mostly to obtain new notes on changesets'''
        cfg = self.config
        timeout = cfg.get('refresh_meta_minutes', 'tracker')
        if timeout>0:
            now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
            if (now-self.last_cset_meta_refresh).total_seconds()/60 > timeout:
                logger.debug('Refreshing all cset meta information')
                self.last_cset_meta_refresh = now
                self.refresh_all_meta()
                #FIXME: It would be sufficient to bump generation if something relevant changed, like notes count
                self.new_generation()

    def refresh_all_meta(self):
        for cset_id in self.area_chgsets:
            self.refresh_cset_meta(cset_id)

    def refresh_cset_meta(self, cset_id):
        chgset = self.api.ChangesetGet(cset_id, include_discussion=True)
        self.area_chgsets_info[cset_id]['meta'] = chgset

    def preprocess_all_csets(self):
        for cset_id in self.area_chgsets:
            self.cset_preprocess(cset_id)
            
    def cset_preprocess(self, cid):
        '''Preprocess cset, i.e. compute various information based on meta, tag info or
           other data'''
        csets = self.area_chgsets
        chginfo = self.area_chgsets_info
        meta = chginfo[cid]['meta']
        summary = chginfo[cid]['summary']
        if not hasattr(chginfo[cid], 'misc'):
            misc = {}
            chginfo[cid]['misc'] = misc
            user = meta['user']
            misc['user_colour'] = self.colours.get_colour(user)
        else:
            misc = chginfo[cid]['misc']
            
        if self.area_chgsets_info[cid]['meta']['open'] == 'true' or not hasattr(misc, 'timestamp_type'):
            self.refresh_cset_meta(cid)
            (tstype, timestamp) = oc.Changeset.get_timestamp(meta)
            ts_type2txt = { 'created_at': 'Started', 'closed_at': 'Closed' }
            misc['timestamp_type'] = tstype
            misc['timestamp_type_txt'] = ts_type2txt[tstype]
            misc['timestamp'] = timestamp
        if cid in self.chgsets_new:
            misc['state'] = 'new'
        else:
            misc['state'] = 'old'

        tagdiff = chginfo[cid]['tagdiff']
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

        tags = chginfo[cid]['tags']
        misc['dk_address_node_changes'] = len([d for d in tags if d.startswith('osak:identifier')])

    def cset_evict(self, cid):
        if cid in self.chgsets:
            self.chgsets.remove(cid)
        if cid in self.area_chgsets:
            self.area_chgsets.remove(cid)
            del self.area_chgsets_info[cid]

    def cut_horizon(self):
        cfg = self.config
        htype = cfg.get('horizon_type', 'tracker')
        removed = False
        if htype == 'sliding':
            hrs = cfg.get('horizon_hours', 'tracker')
            horizon_s = hrs*3600
            now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
            for cset_id in self.area_chgsets[::-1]:
                if not self.area_chgsets_info[cset_id]['meta']['open']:
                    ts = oc.Changeset.get_timestamp(self.area_chgsets_info[cset_id]['meta'])[1]
                    age_s = (now-ts).total_seconds()
                    if age_s > horizon_s:
                        logger.debug('Cset {} old, dropping'.format(cset_id))
                        self.cset_evict(cset_id)
                        removed = True
                    else:
                        logger.debug('Cset {} (ts={}, age={}s) within horizon {}'.format(cset_id, ts, age_s, horizon_s))
        if removed:
            self.new_generation()
        logger.debug('id of state is {}'.format(id(self)))

    def new_generation(self):
        if not hasattr(self, 'generation'):
            self.generation = 0
        else:
            self.generation += 1
        self.generation_timestamp = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)

    def load_backend(self, backend, config):
        logger.debug("Load backend {}".format(backend))
        back = importlib.import_module(backend['type'])
        back = reload(back) # In case it changed
        b = back.Backend(config, backend)
        self.backends.append(b)

    def run_backends(self):
        self.preprocess_all_csets()
        for b in self.backends:
            b.print_state(self)
        self.chgsets_new = []

    def reload_backends(self, config):
        self.backends = []
        #for b in self.backend_modules:
        #    reload(b)
        for back in self.backend_list:
            self.load_backend(back, config, back)

def save_state(state, fname='state.pickle'):
    logger.debug("Saving state to '{}'".format(fname))
    with open(fname, 'w') as f:
        pickle.dump(state, f)

def load_state(fname='state.pickle'):
    logger.debug("Loading state from '{}'".format(fname))
    with open(fname, 'r') as f:
        return pickle.load(f)

def print_stats(bytes_in, bytes_out):
    logger.debug('Memory usage: %s (kb)' % resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    logger.debug('Network usage: In={0}k, Out={1}k'.format(bytes_in/1024, bytes_out/1024))

def fetch_diff(state, seqno, ctype, geojson=None, bounds=None):
    areafile = state.areafile
    args = ["./filter.py", "-a", state.osm_api_url, "-p", "-s", str(seqno), "-t", ctype, "-l", state.log_level]
    if areafile:
        args += ["-A", areafile]
    if geojson:
        args += ["-g", geojson]
    if bounds:
        args += ["-B", bounds]
    timeout = state.config.get('cset_processing_time_max_s', 'tracker')
    if timeout:
        args += ["-U", str(timeout)]

    while True:
        try:
            logger.debug("Calling '{}'".format(args))
            out = subprocess.check_output(args)
            logger.debug("Call returned: '{}'".format(args, out))
            break
        except subprocess.CalledProcessError as e:
            logger.warning('*** Error calling filter.py: {}'.format(e))
            time.sleep(60)

    #out = json.loads(out)
    out = out.split('DATA-SEPARATOR-MAGIC: ')[1]
    out = pickle.loads(out)
    return out

# def buildGeoJsonDiff(cid, basename):
#     logger.debug('Build GeoJson for {}'.format(cid))
#     fname = basename.format(id=cid)
#     cset = OsmChangeset.Changeset(cid)
#     cset.downloadMeta()
#     cset.downloadData()
#     #cset.downloadHistory()
#     with open(fname, 'w') as f:
#         json.dump(cset.getGeoJsonDiff(), f)
#     logger.debug('Done building GeoJson for {}'.format(cid))

def process_diff_result(state, out, track_nonfiltered):
    seqno = out['diff']['seqno']

    chgsets = out['changesets']
    area_chgsets = out['area_changesets']
    area_chgsets_info = out['area_changesets_info']
    err_chgsets = out['err_changesets']
    logger.debug('Changesets: {}, area changesets: {}, changesets w. errors: {}'.format(len(chgsets), len(area_chgsets), len(err_chgsets)))

    if track_nonfiltered:
        for c in chgsets:
            if not c in state.chgsets:
                state.chgsets.append(c)
    for c in area_chgsets:
        if not c in state.area_chgsets:
            state.area_chgsets.append(c)
            state.chgsets_new.append(c)
        # Newer is better, ie. allow overwrite of previous data (cset might have been
        # partial in previous update)
        #buildGeoJsonDiff(c)
        state.area_chgsets_info[c] = area_chgsets_info[c]

    for c in err_chgsets:
        if not c in state.err_chgsets:
            state.err_chgsets.append(c)
            logger.info('Received a changeset with errors, id={}'.format(c))

    state.metrics['bytes_in'] += out['bytes_in']
    state.timestamp = out['diff']['timestamp']
    if not hasattr(state, 'first_timestamp'):
        state.first_timestamp = state.timestamp
    state.latest_seqno = seqno
    if not hasattr(state, 'first_seqno'):
        state.first_seqno = seqno

    # True if any updates found
    return (track_nonfiltered and len(chgsets) > 0) or len(area_chgsets) > 0

def fetch_and_process_diff(state, seqno, ctype, track_nonfiltered):
    logger.debug('Fetching and process diff seqno {}'.format(seqno))
    start = time.time()
    out = fetch_diff(state, seqno, ctype, state.geojson, state.bounds)
    result = process_diff_result(state, out, track_nonfiltered)

    end = time.time()
    elapsed = end-start
    state.processing_timing.append((elapsed, ctype, seqno, start, end))
    state.processing_timing.sort(key=lambda tup: tup[0])
    state.processing_timing = state.processing_timing[:5]
    logger.debug('Handling diff {} took {:.2}s'.format(seqno, elapsed))
    logger.debug('Processing history:')
    for hh in state.processing_timing:
        if hh[0]>45:
            logger.warn('  type={} seqno={} elapsed={} (start={} end={})'.format(hh[1], hh[2], int(hh[0]), hh[3], hh[4]))

    return result

def js_datetime_filter(value):
    '''Jinja2 filter formatting timestamps in format understood by javascript'''
        # See javascript date/time format: http://tools.ietf.org/html/rfc2822#page-14
    JS_TIMESTAMP_FMT = '%a, %d %b %Y %H:%M:%S %z'
    return value.strftime(JS_TIMESTAMP_FMT)

def utc_datetime_filter(value):
    TIMESTAMP_FMT = '%Y:%m:%d %H:%M:%S'
    return value.strftime(TIMESTAMP_FMT)

def parse_opts(argv, state):
    state.max_threads = None
    state.reloaded = False
    state.history = None
    state.history_end = None
    state.dtype = 'minute'
    state.seqno = None
    state.areafile = None
    state.track_nonfiltered = False
    state.backends = []
    state.geojson = None
    state.bounds = None
    state.next_lag = 10 # How much we lag osm timestamps on updates
    state.fast_track = False
    #log_level = 'INFO'

    ## Old above

    parser = argparse.ArgumentParser(description='OSM Analytic Difference Engine')
    parser.add_argument('-c', dest='config_file', default='config.json', help='Set configuration file name')
    parser.add_argument('-B', dest='bounds_file', help='Set changeset boundary file name')
    parser.add_argument('-A', dest='areafile', help='Set area filter polygon')
    parser.add_argument('-a', dest='osm_api_url', help='OpenStreetMap API URL')
    parser.add_argument('-H', dest='history', action='append', help='Define how much history to fetch')
    parser.add_argument('-s', dest='seqno', help='Set initial sequence number')
    parser.add_argument('-T', dest='max_threads', help='Define maximum number of additional worker threads to use (zero means single threaded operation)')
    parser.add_argument('-l', dest='log_level', default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], help='Set the log level')
    parser.add_argument('-L', dest='load_state', action='store_true', help='Load state from previous snapshot')

    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level, None))

    if args.load_state:
        state = load_state()
        state.history = None
        state.reloaded = True
        state.new_generation()
        return state

    if args.config_file:
        logger.info("Loading config file '{}'".format(args.config_file))
        state.config = config.Config()
        try:
            state.config.load(args.config_file)
        except Exception as e:
            print "Error parsing config file: '{}': {}".format(args.config_file, e)
            sys.exit(-1)

    state.log_level = args.log_level
    state.areafile = args.bounds_file if args.bounds_file else state.config.get('bounds_filename', 'tracker')
    if args.history:
        state.history = HumanTime.human2date(args.history[0]) if len(args.history)>0 else HumanTime.human2date(state.config.get('history', 'tracker'))
        state.history_end = HumanTime.human2date(args.history[1]) if len(args.history)>1 else None
    state.seqno = args.seqno if args.seqno else state.config.get('initial_sequenceno', 'tracker')
    state.max_threads = args.max_threads if args.max_threads else state.config.get('max_threads', 'tracker')
    if state.config.get('geojsondiff-filename', 'tracker'):
        state.geojson = state.config.get('path', 'tracker')+state.config.get('geojsondiff-filename', 'tracker')
    if state.config.get('bounds-filename', 'tracker'):
        state.bounds = state.config.get('path', 'tracker')+state.config.get('bounds-filename', 'tracker')
    state.areafile = args.areafile if args.areafile else state.config.get('area-filter', 'tracker')
    state.osm_api_url = args.osm_api_url if args.osm_api_url else state.config.get('osm_api_url', 'tracker', default='https://api.openstreetmap.org')

    state.env = jinja2.Environment(loader=jinja2.FileSystemLoader(state.config.getpath('template_path', 'tracker')))
    state.env.filters['js_datetime'] = js_datetime_filter
    state.env.filters['utc_datetime'] = utc_datetime_filter

    blist = state.config.get('backends', 'tracker')
    if not blist:
        print 'No backends specified'
        sys.exit(-1)
        
    for backend in blist:
        state.load_backend(backend, state.config)
    state.backend_list = blist

    if state.seqno:
        logger.debug('Initial sequence number: {}'.format(state.seqno))
    if state.history:
        if state.history_end:
            logger.debug('History period: {} - {}'.format(state.history, state.history_end))
        else:
            logger.debug('History back to: {}'.format(state.history))

    return state


#     if (state.history):
#         state.ptr = {}
#         if state.history_minute_based:
#             # Step back using minute diffs only
#             state.ptr['minute'] = state.dapi.get_seqno_le_timestamp('minute',
#                                 state.history, state.head['minute'])
#             logger.debug('Minute pointer: {0}'.format(state.ptr['minute']))
#         else:
#             # Slow at first, then faster (day granularity)
#             state.ptr['minute'] = state.dapi.get_seqno_le_timestamp('minute',
#                                 max(state.history, state.head['hour'].timestamp()), state.head['minute'])
#             state.ptr['hour'] = state.dapi.get_seqno_le_timestamp('hour',
#                                 max(state.history, state.head['day'].timestamp()), state.head['hour'])
#             state.ptr['day'] = state.dapi.get_seqno_le_timestamp('day', state.history, state.head['day'])
#             logger.debug('Pointers: {0}, {1}, {2}'.format(state.ptr['day'], state.ptr['hour'], state.ptr['minute']))


def update_diffs(state, direction, max_threads=None):
    '''Fetch csets between state 'pointer' (excluding) and 'head' (including) in the specified direction.'''
    
    if max_threads:
        processes=int(max_threads)
    else:
        processes=mp.cpu_count()
    processes = min(processes, abs(state.head.sequenceno()-state.pointer.sequenceno()))
    logger.debug('Processes: {}'.format(processes))
    if processes>1:
        #pool = mp.Pool(processes=processes, maxtasksperchild=1)
        pool = mp.Pool(processes=processes)

    if hasattr(state, 'pointer_end'):
        pointer_end = state.pointer_end
    else:
        pointer_end = state.head

    #for tt in ('day', 'hour', 'minute'):
    if state.pointer.sequenceno() != pointer_end:

        if direction<0:
            logger.debug('Fetch diffs: pointer_end={} pointer={}'.format(pointer_end.sequenceno(), state.pointer.sequenceno()))
            r = range(pointer_end.sequenceno(), state.pointer.sequenceno(), -1)
        else:
            logger.debug('Fetch diffs: pointer={} pointer_end={}'.format(state.pointer.sequenceno(), pointer_end.sequenceno()))
            r = range(state.pointer.sequenceno()+1, pointer_end.sequenceno()+1)

        logger.debug('Segnos ({}) to fetch: {}'.format(len(r), r))
        if processes>1:
            #results = [pool.apply_async(fetch_diff, args=(state,seqno,state.dtype,state.geojson,state.bounds)) for seqno in r]
            results = []
            for seqno in r:
                res = pool.apply_async(fetch_diff, args=(state,seqno,state.dtype,state.geojson,state.bounds))
                results.append(res)
                logger.debug('Queued seqno {} in result {}'.format(seqno, res))

            logger.debug('Results ({}): {}'.format(len(results), results))
            for r in results:
                logger.debug('Fetching result from {}'.format(r))
                out = r.get()
                logger.debug('Got result from {}, seqno={}'.format(r, out['diff']['seqno']))
                if process_diff_result(state, out, state.track_nonfiltered):
                    state.sort_csets()
                    state.new_generation()
                # Update backends after every diff
                state.run_backends()

        else:
            for seqno in r:
                sys.stdout.flush()
                if fetch_and_process_diff(state, seqno, state.dtype, state.track_nonfiltered):
                    state.sort_csets()
                    state.new_generation()
                # Update backends after every diff
                state.run_backends()

    if processes>1:
        pool.close()

    state.pointer = pointer_end

def continuous_update(state, direction=1):
    state.head = state.dapi.get_state(state.dtype, seqno=None)
    start = time.time()
    update_diffs(state, max_threads=state.max_threads, direction=direction)
    end = time.time()
    elapsed = end-start
    delay = min(60, max(0, 60-elapsed))
    if not hasattr(state, 'pointer_end'):
        logger.debug('Processing to ptr {} took {:.2}s. Sleeping {}s'.format(state.pointer, elapsed, delay))
        time.sleep(delay)


# def continuous_update_old(state):
#     seqno = state.pointer.sequenceno()
#     now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
#     start = time.time()
#     logger.debug('Now is {0} (UTC)'.format(now))
#     logger.debug('Pointer is: {}'.format(state.pointer))
#     logger.debug('Head is:'.format(state.head))

#     # FIXME: Head is fetched also in history
#     if fetch_and_process_diff(state, seqno, state.dtype, state.track_nonfiltered):
#         state.new_generation()

#     if state.pointer.sequenceno() == state.head.sequenceno():
#         logger.debug('Area changesets:')
#         state.run_backends()
#         logger.debug('Size of: List of changesets {}, area changeset info {}'.format(sys.getsizeof(state.chgsets),
#                                                                                       sys.getsizeof(state.area_chgsets_info)))
#     else:
#         logger.info('[{0}]'.format(state.pointer.sequenceno()))

#     end = time.time()
#     elapsed = end-start
#     lag = now-state.pointer.timestamp()
#     state.lag_stats[min(lag.seconds, len(state.lag_stats)-1)] += 1
#     #logger.debug('Lag correction %.1fs' % (lag_corr))
#     logger.debug('Lag:  Curr {}s stats {}'.format(lag.seconds, state.lag_stats))
#     print_stats(state.metrics['bytes_in'], 0)

#     seqno = state.pointer.sequenceno()
#     if seqno == state.head.sequenceno():
#         delay = min(60, max(0, 60-elapsed))
#         if state.fast_track:
#             next_ts = state.head.timestamp() + datetime.timedelta(seconds=60)
#             now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
#             next_s = (next_ts - now).seconds
#             if next_s > 0:
#                 delay = min(next_s+next_lag, delay)
#             logger.debug('last ts {}, next ts {}, next s {}, now {}'.format(state.head.timestamp(), next_ts, next_s, now))
#         polls = 0
#         while seqno == state.head.sequenceno():
#             if delay <= 5:
#                 state.aggr_poll_stat[0] += 1
#             else:
#                 state.aggr_poll_stat[1] += 1
#             logger.debug('Relaxing for %.1fs, poll #%d' % (delay, polls))
#             time.sleep(delay)
#             # If there was no new minutely state after waiting, we
#             # poll more aggressively a few times
#             if polls < 2:
#                 delay = 5
#             else:
#                 delay = 60
#             state.head = state.dapi.get_state(state.dtype, seqno=None)
#             polls += 1
#         state.poll_stats[min(polls, len(state.poll_stats)-1)] += 1
#         if state.fast_track:
#             if polls==1:
#                 next_lag -= 1
#             if polls>1:
#                 next_lag += min(10, polls)
#             logger.debug('Next lag {}s'.format(next_lag))
#             logger.debug('Poll: Fast {} slow {} stats {}'.format(state.aggr_poll_stat[0],
#                                                                   state.aggr_poll_stat[1], state.poll_stats))
#     seqno = seqno+1
#     state.pointer = state.dapi.get_state(state.dtype, seqno)
#     logger.debug('Trying to catch-up, {0}..{1}, {2} to go'.format(seqno, state.head.sequenceno(),
#                                                                    state.head.sequenceno()-seqno))

def main(argv):
    global reload_backends
    def sig_handler(signum, frame):
        logger.debug('Caught signal: {}'.format(signum))
        global reload_backends
        reload_backends = True

    reload_backends = False
    state = TrackedState()
    state = parse_opts(argv, state)

    logger.debug('Using api: {}'.format(state.osm_api_url))
    state.api = osmapi.OsmApi(api=state.osm_api_url)
    state.dapi = osmdiff.OsmDiffApi()

    state.dapi.update_head_states()
    state.head = state.dapi.get_state(state.dtype)
    if state.history:
        state.pointer = state.dapi.get_seqno_le_timestamp('minute', state.history, state.head)
        if state.history_end:
            state.pointer_end = state.dapi.get_seqno_le_timestamp('minute', state.history_end, state.head)
    elif not state.reloaded:
        state.pointer = state.head

    if state.history_end:
        logger.debug('Head={} pointer={}, pointer_end={}'.format(state.head, state.pointer, state.pointer_end))
    else:
        logger.debug('Head={} pointer={}'.format(state.head, state.pointer))

    signal.signal(signal.SIGHUP, sig_handler)

    state.poll_stats = [0 for x in range(60)]
    state.lag_stats = [0 for x in range(120)]
    state.aggr_poll_stat = [0,0]
    state.processing_timing = []

    if hasattr(state, 'pointer_end') and state.pointer >= state.pointer_end:
        direction = 1
    else:
        direction = -1 # Backward initially

    while True:
        try:
            continuous_update(state, direction)
            direction = 1 # Forward after first fetch
            state.cut_horizon()
            state.try_refresh_meta()

        except (osmapi.ApiError, osmdiff.OsmDiffException, urllib2.HTTPError, urllib2.URLError) as e:
            logger.error('Error retrieving data: '.format(e))
            logger.error(traceback.format_exc())
            time.sleep(60)

        if reload_backends:
            save_state(state)
            state.reload_backends(state.config)
            state.new_generation()
            reload_backends = False
        if hasattr(state, 'pointer_end') and state.pointer >= state.pointer_end:
            logger.info('Reached end of period to fetch ({} - {}) - terminating'.format(state.history, state.history_end))
            sys.exit(0)

if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except:
        logger.error("Unexpected error: "+str(sys.exc_info()[0]))
        raise
