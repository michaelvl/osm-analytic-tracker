import re
from shapely import geometry

class BBox(object):
    def __init__(self, x1=None, y1=None, x2=None, y2=None):
        self.x1 = None
        self.y1 = None
        self.x2 = None
        self.y2 = None
        self.add_point(x1, y1)
        self.add_point(x2, y2)

    def to_dict(self):
        if self.x1:
            return {'lat_min': self.y1, 'lat_max': self.y2, 'lon_min': self.x1, 'lon_max': self.x2}
        else:
            return None

    def get_bbox(self):
        return geometry.box(self.x1, self.y1, self.x2, self.y2)

    def add_point(self, x, y):
        if x is None or y is None:
            return
        if self.x1 is None:
            self.x1 = self.x2 = x
            self.y1 = self.y2 = y
        else:
            self.x1 = min(self.x1, x)
            self.x2 = max(self.x2, x)
            self.y1 = min(self.y1, y)
            self.y2 = max(self.y2, y)

class Poly(object):
    def __init__(self):
        self.poly = geometry.Polygon

    def load(self, fname):
        flt = r'[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?'
        ptre = re.compile('\s*('+flt+')\s+('+flt+')')
        poly = []
        with open(fname) as f:
            for ln in f.readlines():
                m = ptre.match(ln)
                if m:
                    poly.append((float(m.group(1)), float(m.group(5))))
        self.poly = geometry.Polygon(poly)

    def contains(self, x, y):
        pt = geometry.Point(x, y)
        return self.poly.contains(pt)

    def contains_chgset(self, chg):
        if set(['min_lon', 'min_lat', 'max_lon', 'max_lat']).issubset(chg.keys()):
            x1 = float(chg['min_lon'])
            y1 = float(chg['min_lat'])
            x2 = float(chg['max_lon'])
            y2 = float(chg['max_lat'])
            return self.contains(x1 ,y1, x2, y2)
        return False

    def contains_bbox(self, bbox):
        return self.contains(bbox['lon_min'], bbox['lat_min'], bbox['lon_max'], bbox['lat_max'])

    def contains(self, x1, y1, x2, y2):
        '''Test against bbox from points (x1,y1) and (x2,y2)'''
        box = geometry.box(x1, y1, x2, y2)
        if self.poly.intersects(box):
            return True
        small = 0.000001
        if abs(x1-x2)<small or abs(y1-y2)<small:
            # Point-sized box does not intersect with anything
            return self.poly.intersects(geometry.Point(x1, y1))
        return False

    def bbox(self):
        return self.poly.bounds

    def center(self):
        bbox = self.bbox()
        return ((bbox[2]+bbox[0])/2, (bbox[3]+bbox[1])/2)

    def __len__(self):
        return len(self.poly.exterior.xy[0])
