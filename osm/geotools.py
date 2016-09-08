import math

# https://en.wikipedia.org/wiki/Earth_radius
EARTH_RADIUS_M=(6384+6353)/2*1000

def haversine(lon1, lat1, lon2, lat2):
    # Degrees to radians 
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])

    # https://en.wikipedia.org/wiki/Haversine_formula
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))
