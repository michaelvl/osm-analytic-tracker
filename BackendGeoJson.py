from __future__ import print_function
import sys
from db import show_brief as db_show_brief
import Backend
import json
import datetime, pytz
import logging
import tempfilewriter
import osm.changeset
from os import listdir, remove
from os.path import isfile, join
import re

logger = logging.getLogger(__name__)

class Backend(Backend.Backend):
    def __init__(self, globalconfig, subcfg):
        super(Backend, self).__init__(globalconfig, subcfg)
        self.cfg = subcfg
        self.click_url = subcfg['click_url']
        self.exptype = subcfg['exptype']
        self.path = self.build_filename(globalconfig, subcfg, filename_key=None)
        if self.exptype == 'cset-files':
            self.geojson = subcfg['geojsondiff-filename']
            self.bbox = subcfg['bounds-filename']
            self.list_fname = None
            self.last_cleanup = None
        else:
            self.list_fname = subcfg['filename']
            self.geojson = None
            self.bbox = None

    def print_state(self, db):
        if self.generation != db.generation:
            self.generation = db.generation
            if self.exptype == 'cset-bbox':
                self.print_chgsets_bbox(db)
            elif self.exptype == 'cset-files':
                now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
                # TODO: Consider using a tailing cursor?
                since = now-datetime.timedelta(minutes=30)
                if self.last_cleanup:
                    cleanup_age_s = (now-self.last_cleanup).total_seconds()
                if not self.last_cleanup or cleanup_age_s>2*3600:
                    logger.info('Doing full export and cleanup')
                    since = None
                files = self.print_chgsets_files(db, since)
                if not since:
                    self.cleanup_old_files(files)
                    self.last_cleanup = now

    def add_cset_bbox(self, cset, db, geoj):
        cid = cset['cid']
        meta = db.chgset_get_meta(cid)
        info = db.chgset_get_info(cid)
        # Changesets that only modify relation members do not have a bbox
        if set(['min_lon', 'min_lat', 'max_lon', 'max_lat']).issubset(meta.keys()):
            (x1, x2, y1, y2) = (meta['min_lat'], meta['max_lat'], meta['min_lon'], meta['max_lon'])
            colour = '#'+info['misc']['user_colour']
            if 'comment' in meta['tag'].keys():
                comment = meta['tag']['comment']
            else:
                comment = '*** no comment ***'
            utfmeta = {}
            for k in meta:
                if isinstance(meta[k], datetime.datetime):
                    utfmeta[k] = str(meta[k])
                else:
                    utfmeta[k] = meta[k]
            utfmeta['discussion'] = meta['discussion'][:]
            for n in utfmeta['discussion']:
                n['date'] = str(n['date'])
            feature = { "type": "Feature",
                     "properties": { 'color': colour, 'id': meta['id'],
                                     'meta': utfmeta,
                                     'url': "http://www.openstreetmap.org/changeset/"+str(meta['id']),
                                     'visualdiff': self.click_url.format(cid=meta['id'])},
                     "geometry": {
                         #"type": "Polygon",
                         #"coordinates": [[[y1,x1],[y2,x1],[y2,x2],[y1,x2],[y1,x1]]]
                         "type": "LineString",
                         "coordinates": [[y1,x1],[y2,x1],[y2,x2],[y1,x2],[y1,x1]]
                     }
            }
            geoj['features'].append(feature)

    def print_chgsets_bbox(self, db):
        '''Generate a single file with all bboxes of all changesets'''
        geoj = { "type": "FeatureCollection",
                 "features": [] }
        if db:
            for c in db.chgsets_find(state=db.STATE_DONE, sort=False):
                self.add_cset_bbox(c, db, geoj)

        logger.debug('Data sent to json file={}'.format(geoj))
        with tempfilewriter.TempFileWriter(join(self.path, self.list_fname)) as f:
            f.write(json.dumps(geoj))

    def print_chgsets_files(self, db, last_update):
        '''Generate two files for each cset, a geojson file containing changets changes
           and one containing bbox of changeset'''
        files = [] # List of files we generated
        if db:
            for c in db.chgsets_find(state=db.STATE_DONE, after=last_update, sort=False):
                try:
                    fn = self.geojson.format(id=c['cid'])
                    logger.info("Export cset {} diff to file '{}', last update {}".format(c['cid'], fn, last_update))
                    cset = osm.changeset.Changeset(id=c['cid'], api=None)
                    meta = db.chgset_get_meta(c['cid'])
                    cset.meta = meta
                    info = db.chgset_get_info(c['cid'])
                    cset.data_import(info)
                    with tempfilewriter.TempFileWriter(join(self.path, fn)) as f:
                        json.dump(cset.getGeoJsonDiff(), f)
                        files.append(fn)

                    b = '{},{},{},{}'.format(cset.meta['min_lat'], cset.meta['min_lon'],
                                             cset.meta['max_lat'], cset.meta['max_lon'])
                    fn = self.bbox.format(id=c['cid'])
                    logger.info("Export cset {} bounds to file '{}'".format(c['cid'], fn))
                    with tempfilewriter.TempFileWriter(join(self.path, fn)) as f:
                        f.write(b)
                        files.append(fn)
                except Exception as e:
                    exc_info = sys.exc_info()
                    logger.error('Error exporting cid {}: {}'.format(c['cid'], exc_info))
                    logger.error('Cset data: {}'.format(c))
                    #raise exc_info[1], None, exc_info[2]

            db_show_brief(None, db, False)
        return files

    def cleanup_old_files(self, files):
        oldfiles = [f for f in listdir(self.path) if isfile(join(self.path, f)) and f not in files]
        ptrn = '(^' +  re.escape(self.geojson) + '$)|(^' +  re.escape(self.bbox) + '$)'
        ptrn = ptrn.replace('\{id\}', '\d+')
        reptrn = re.compile(ptrn)
        oldfiles = [f for f in oldfiles if reptrn.match(f)]
        if oldfiles:
            logger.info('Removing old files: {}'.format(oldfiles))
            for f in oldfiles:
                remove(join(self.path, f))
