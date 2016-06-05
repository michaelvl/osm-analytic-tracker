from __future__ import print_function
import Backend
import ColourScheme as col
import json
import datetime
import logging

logger = logging.getLogger(__name__)

class Backend(Backend.Backend):
    def __init__(self, config, subcfg):
        super(Backend, self).__init__(config, subcfg)
        self.list_fname = config.getpath('path', 'BackendGeoJson')+'/'+subcfg['filename']
        self.click_url = subcfg['click_url']
        self.colours = col.ColourScheme()

        self.generation = None
        self.print_chgsets(None, None)

    def print_state(self, state):
        if self.generation != state.generation:
            self.generation = state.generation
            if len(state.area_chgsets) > 0:
                self.print_chgsets(state.area_chgsets,
                                   state.area_chgsets_info)

    def pprint(self, txt):
        #print(txt.encode('utf8'), file=self.f)
        print(txt, file=self.f)
        #print('*'+txt)

    def start_file(self, fname):
        self.f = open(fname, 'w')

    def end_file(self):
        self.f.close()
        self.f = None

    def add_cset_bbox(self, geoj, meta):
        # Changesets that only modify relation members do not have a bbox
        if set(['min_lon', 'min_lat', 'max_lon', 'max_lat']).issubset(meta.keys()):
            (x1, x2, y1, y2) = (meta['min_lat'], meta['max_lat'], meta['min_lon'], meta['max_lon'])
            colour = '#'+self.colours.get_colour(meta['user'])
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

    def print_chgsets(self, csets, info):
        geoj = { "type": "FeatureCollection",
                 "features": [] }
        if csets and len(csets) > 0:
            for chgid in csets[::-1]:
                data = info[chgid]
                self.add_cset_bbox(geoj, data['meta'])

        self.start_file(self.list_fname)
        logger.debug('Data sent to json file={}'.format(geoj))
        self.pprint(json.dumps(geoj))
        self.end_file()
