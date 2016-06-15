#!/usr/bin/python

import sys, getopt
from osmapi import OsmApi
import pprint
import json
import OsmChangeset

def main(argv):
    debug = False
    meta = False
    changes = False
    history = False
    summary = False
    raw_summary = False
    geojson = None
    bbox = False
    bounds = None
    csetid = None
    apiurl = None
    tags = False
    try:
        opts, args = getopt.getopt(argv, "a:dg:i:mchsb:BTS")
    except getopt.GetoptError:
        print "..."
        sys.exit(-1)
    for opt, arg in opts:
        if opt == '-a':
            apiurl = arg
        if opt == '-d':
            debug = True
        if opt == '-m':
            meta = True
        if opt == '-h':
            history = True
        if opt == '-s':
            summary = True
        if opt == '-S':
            raw_summary = True
        if opt == '-c':
            changes = True
        if opt == '-g':
            geojson = arg
        if opt == '-B':
            bbox = True
        if opt == '-b':
            bounds = arg
        if opt == '-i':
            csetid = int(arg)
        if opt == '-T':
            tags = True

    if apiurl:
        cset = OsmChangeset.Changeset(csetid, api=apiurl)
    else:
        cset = OsmChangeset.Changeset(csetid)
    cset.apidebug = debug

    cset.downloadMeta()

    if changes or history or summary or geojson:
        cset.downloadData()
        cset.downloadHistory()

    #cset.getReferencedElements()

    if meta:
        if debug:
            print '== Changeset info ======='
        pprint.pprint(cset.meta)
    if bbox:
        if debug:
            print '== Changeset bbox ======='
        print '[[{},{}],[{},{}]]'.format(cset.meta['min_lat'], cset.meta['min_lon'],
                                   cset.meta['max_lat'], cset.meta['max_lon'])
    if bounds:
        if debug:
            print '== Changeset bounds ======='
        b = '[[{},{}],[{},{}]]'.format(cset.meta['min_lat'], cset.meta['min_lon'],
                                   cset.meta['max_lat'], cset.meta['max_lon'])
        if bounds=='-':
            print(b)
        else:
            with open(bounds, 'w') as f:
                f.write(b)
    if changes:
        if debug:
            print '== Changes ======='
        pprint.pprint(cset.changes)
    if history:
        if debug:
            print '== History ======'
        pprint.pprint(cset.hist)
    if summary:
        if debug:
            print '== Summary ======'
        cset.buildSummary()
        cset.printSummary()
        if debug:
            print '== Diffs ======'
        cset.printDiffs()
        if raw_summary:
            if debug:
                print '== Raw summary ======'
            print cset.summary
            if debug:
                print '== Raw tagdiff ======'
            print cset.tagdiff
    if tags:
        if debug:
            print '== Tags ======'
        print cset.tags
    if geojson:
        if debug:
            print '== GeoJsonDiff ======'
        if geojson=='-':
            pprint.pprint(cset.getGeoJsonDiff())
        else:
            with open(geojson, 'w') as f:
                json.dump(cset.getGeoJsonDiff(), f)


if __name__ == "__main__":

    sys.path.insert(0, '/home/mvl/workspace/osm-updated/osmapi/osmapi/')

    try:
        main(sys.argv[1:])
    except:
        print "Unexpected error:", sys.exc_info()[0]
        raise
