
class GeoJson(object):
    def __init__(self):
        self.data = {"type": "FeatureCollection",
                     "features": [] }

    def getData(self):
        return self.data

    def addProperty(self, f, prop, val):
        f['properties'][prop] = u'{}'.format(val)

    def addColour(self, f, col):
        f['properties']['color'] = '#{}'.format(col)

    def addPoint(self, lon, lat):
        p = { "type": "Feature",
              "geometry": {
                  "type": "Point",
                  "coordinates": [lon, lat]
              },
              "properties": {}
          }
        self.data['features'].append(p)
        return p

    def addLineString(self):
        l = { "type": "Feature",
              "geometry": {
                  "type": "LineString",
                  "coordinates": []
              },
              "properties": {}
          }
        self.data['features'].append(l)
        return l

    def addLineStringPoint(self, l, lon, lat):
        l['geometry']['coordinates'].append([lon,lat])
