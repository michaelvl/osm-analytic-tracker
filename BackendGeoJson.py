from __future__ import print_function
import Backend
import json
import datetime
import logging
import tempfilewriter

logger = logging.getLogger(__name__)

class Backend(Backend.Backend):
    def __init__(self, globalconfig, subcfg):
        super(Backend, self).__init__(globalconfig, subcfg)
        self.list_fname = globalconfig.getpath('path', 'tracker')+'/'+subcfg['filename']
        self.click_url = subcfg['click_url']

    def print_state(self, db):
        if self.generation != db.generation:
            self.generation = db.generation
            if db.chgsets_count() > 0:
                self.print_chgsets(db)

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

    def print_chgsets(self, db):
        geoj = { "type": "FeatureCollection",
                 "features": [] }
        if db:
            for c in db.chgsets_find(state=db.STATE_DONE):
                self.add_cset_bbox(c, db, geoj)

        logger.debug('Data sent to json file={}'.format(geoj))
        with tempfilewriter.TempFileWriter(self.list_fname) as f:
            f.write(json.dumps(geoj))
