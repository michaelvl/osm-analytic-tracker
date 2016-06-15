#!/usr/bin/python

import sys
import argparse
import OsmDiff as osmdiff
import pprint
import json, pickle
import Poly
import osmapi
import OsmChangeset
import logging

logger = logging.getLogger(__name__)

def fetch_and_process_diff(dapi, osm_api_url, seqno, ctype, area=None, debug=0, strict_inside_check=True):
    chgsets = []
    area_chgsets = []
    err_chgsets = []

    chgsets = dapi.get_diff_csets(seqno, ctype)
    logger.debug('Found {} changesets in diff {}-{}'.format(len(chgsets), ctype, seqno))

    # diff = dapi.get_diff(seqno, ctype)
    # # First, locate changesets
    # for ac in diff.get_data():
    #     data = ac['data']
    #     cset_id = int(data['changeset'])
    #     if cset_id not in chgsets:
    #         chgsets.append(cset_id)
    #         #print u'user=\'{}\', chgset {} timestamp {}'.format(data['user'], cset_id, data['timestamp'])

    # Read changeset meta and check if within area
    for id in chgsets:
        if id not in area_chgsets:
            #print u'id {}'.format(id)
            c = OsmChangeset.Changeset(id, api=osm_api_url)
            c.apidebug = debug
            c.datadebug = debug
            c.downloadMeta()

            # Check if node and thus changeset is within area (bbox check)
            #pprint.pprint(c.meta)
            if not area or area.contains_chgset(c.meta):
                try:
                    if strict_inside_check:
                        c.downloadData()
                        if c.isInside(area):
                            area_chgsets.append(c)
                    else:
                        area_chgsets.append(c)
                #except IOError as e:
                #    pass
                except osmapi.ApiError as e:
                    logger.error('Failed reading changeset {}: {}'.format(id, e))
                    err_chgsets.append(c)

    return (chgsets, area_chgsets, err_chgsets)

def process_csets(args, csets):
    dtype, seqno, geojson, bbox = (args.dtype, args.seqno, args.geojson, args.bbox)
    stat = {}
    for c in csets:
        truncated = False
        diffs = None
        try:
            c.downloadData()
            c.downloadHistory(maxtime=args.cset_max_time)
            #c.getReferencedElements()
            c.buildSummary(maxtime=args.cset_max_time)
            #print '== Summary, id {} ======'.format(c.id)
            #c.printSummary()
            #print '== Diffs, id {} ======'.format(c.id)
            #c.printDiffs()
            diffs = c.buildDiffList(maxtime=args.cset_max_time)
        except OsmChangeset.Timeout as e:
            truncated = True

        stat[c.id] = {'state': {'truncated': truncated},
                      'source': {'type': dtype, 'sequenceno': seqno},
                      'meta': c.meta, 'summary': c.summary,
                      'tags': c.tags, 'tagdiff': c.tagdiff,
                      'simple_nodes': c.simple_nodes, 'diffs': diffs,
                      'other_users': c.other_users, 'mileage_m': c.mileage}
        if truncated:
            logger.error('Changeset {} not fully processed.'.format(c.id))
        else:
            if geojson:
                fn = geojson.format(id=c.id)
                with open(fn, 'w') as f:
                    json.dump(c.getGeoJsonDiff(), f)

        if bbox:
            #b = '[[{},{}],[{},{}]]'.format(c.meta['min_lat'], c.meta['min_lon'],
            #                               c.meta['max_lat'], c.meta['max_lon'])
            b = '{},{},{},{}'.format(c.meta['min_lat'], c.meta['min_lon'],
                                           c.meta['max_lat'], c.meta['max_lon'])
            fn = bbox.format(id=c.id)
            with open(fn, 'w') as f:
                f.write(b)

        c.unload()

    return stat

def main(argv):
    parser = argparse.ArgumentParser(description='OSM Changeset diff filter')
    parser.add_argument('-p', dest='use_pickle', action='store_true', help='Output state using pickle')
    parser.add_argument('-t', dest='dtype', default='minute', help='OSM diff type to retrieve')
    parser.add_argument('-U', dest='cset_max_time', type=int, default=None, help='Maximum number of seconds to spend on processing a changeset')
    parser.add_argument('-B', dest='bbox', help='Set changeset boundary file name')
    parser.add_argument('-g', dest='geojson', help='Set changeset geojson file name')
    parser.add_argument('-A', dest='areafile', help='Set area filter polygon')
    parser.add_argument('-a', dest='osm_api_url', help='OpenStreetMap API URL', default='https://api.openstreetmap.org')
    parser.add_argument('-s', dest='seqno', type=int, help='Set initial sequence number')
    parser.add_argument('-l', dest='log_level', default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], help='Set the log level')

    args = parser.parse_args()
    if args.seqno:
        args.seqno = int(args.seqno)

    logging.basicConfig(level=getattr(logging, args.log_level, None))

    logger.debug('Diff type:'.format(args.dtype))
    logger.debug('Sequence number:'.format(args.seqno))
    logger.debug('Areafile:'.format(args.areafile))

    if args.areafile:
        area = Poly.Poly()
        area.load(args.areafile)
        logger.debug('Loaded area polygon from \'{0}\' with {1} points.'.format(args.areafile, len(area)))
        logger.debug('bounds={}'.format(area.poly.bounds))

    dapi = osmdiff.OsmDiffApi()
    dapi.update_head_states()

    if args.log_level == 'DEBUG':
        dapi.debug = True

    state = dapi.get_state(args.dtype, args.seqno)

    logger.debug('Fetching and processing')
    (chgsets, area_chgsets, err_chgsets) = fetch_and_process_diff(dapi, args.osm_api_url, args.seqno, args.dtype, area, args.log_level=='DEBUG')
    logger.debug('Area changesets: {}'.format([x.id for x in area_chgsets]))

    logger.debug('Processing csets')
    area_chgsets_info = process_csets(args, area_chgsets)

    res = {
        "state": "OK",
        "diff": {"type": args.dtype, "seqno": args.seqno, "filtered": args.areafile, "timestamp":state.timestamp()},
        "changesets": chgsets,
        "area_changesets": [x.id for x in area_chgsets],
        "area_changesets_info": area_chgsets_info,
        "err_changesets": [x.id for x in err_chgsets],
        "bytes_in": dapi.netstat[0],
        "bytes_out" : 0
    }

    if args.log_level=='DEBUG':
        print '-'*50
        pprint.pprint(res)
        print '-'*50

    logger.debug('Dumping data')
    # If there are debug logs or other spurious printouts from above, we use
    # this separator to separate the pickled data from logs
    print 'DATA-SEPARATOR-MAGIC:',
    if args.use_pickle:
        print pickle.dumps(res)
    else:
        print json.dumps(res)
    return 0

if __name__ == "__main__":
   sys.exit(main(sys.argv[1:]))
