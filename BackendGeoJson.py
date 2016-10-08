from __future__ import print_function
import Backend
import json
import datetime
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
        self.click_url = subcfg['click_url']
        self.exptype = subcfg['exptype']
        self.path = globalconfig.getpath('path', 'tracker')
        if self.exptype == 'cset-files':
            self.geojson = subcfg['geojsondiff-filename']
            self.bbox = subcfg['bounds-filename']
            self.list_fname = None
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
                files = self.print_chgsets_files(db)
                self.cleanup_old_files(files)

    def pprint(self, txt):
        #print(txt.encode('utf8'), file=self.f)
        print(txt, file=self.f)
        #print('*'+txt)

    def start_file(self, fname):
        self.f = open(fname, 'w')

    def end_file(self):
        self.f.close()
        self.f = None

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
            for c in db.chgsets_find(state=db.STATE_DONE):
                self.add_cset_bbox(c, db, geoj)

        logger.debug('Data sent to json file={}'.format(geoj))
        with tempfilewriter.TempFileWriter(join(self.path, self.list_fname)) as f:
            f.write(json.dumps(geoj))

    def print_chgsets_files(self, db):
        '''Generate two files for each cset, a geojson file containing changets changes
           and one containing bbox of changeset'''
        files = [] # List of files we generated
        if db:
            for c in db.chgsets_find(state=db.STATE_DONE):
                fn = self.geojson.format(id=c['cid'])
                logger.info("Export cset {} diff to file '{}'".format(c['cid'], fn))
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
