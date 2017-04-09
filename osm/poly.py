import re
from shapely import geometry

class Poly:
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
            box = geometry.box(x1, y1, x2, y2)
            if self.poly.intersects(box):
                return True
            small = 0.000001
            if abs(x1-x2)<small or abs(y1-y2)<small:
                # Point-sized box does not intersect with anything
                return self.poly.intersects(geometry.Point(x1, y1))
        return None

    def bbox(self):
        return self.poly.bounds

    def center(self):
        bbox = self.bbox()
        return ((bbox[2]+bbox[0])/2, (bbox[3]+bbox[1])/2)

    def __len__(self):
        return len(self.poly.exterior.xy[0])
