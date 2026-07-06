import math
from typing import Optional
from app.schemas import DiscType

def map_discit_category(category: str, speed: Optional[float] = None) -> Optional[DiscType]:
    """Fuzzy-map a DiscIt category to our disc type.

    DiscIt category names vary ("Putter", "Putt & Approach", "Approach Discs",
    "Distance Drivers", ...), so match on keywords and fall back to inferring
    from speed — discs.disc_type is NOT NULL, an unmapped type breaks adds.
    """
    c = (category or "").lower()
    if "putt" in c or "approach" in c:
        return DiscType.putter
    if "mid" in c:
        return DiscType.midrange
    if "distance" in c:
        return DiscType.distance_driver
    if "control" in c or "hybrid" in c or "fairway" in c or "driver" in c:
        return DiscType.fairway_driver
    if speed is not None:
        if speed >= 9:
            return DiscType.distance_driver
        if speed >= 6:
            return DiscType.fairway_driver
        if speed >= 4:
            return DiscType.midrange
        return DiscType.putter
    return None


def parse_float(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def haversine_feet(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points, in feet."""
    earth_radius_ft = 20902231.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * earth_radius_ft * math.asin(math.sqrt(a))


def bearing_between(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing in degrees (0-360, 0 = north) from point 1 to point 2."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dlam = math.radians(lon2 - lon1)

    x = math.sin(dlam) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlam)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def angle_diff(bearing_a: float, bearing_b: float) -> float:
    """Signed smallest difference bearing_a - bearing_b, in (-180, 180].
    Positive = bearing_a is clockwise (right) of bearing_b."""
    diff = (bearing_a - bearing_b) % 360.0
    if diff > 180.0:
        diff -= 360.0
    return diff


def point_in_polygon(lat: float, lon: float, ring: list) -> bool:
    """Ray-casting point-in-polygon test. ring is a list of (lat, lon) tuples
    (closed or open). Used for fairway-hit stats."""
    if len(ring) < 3:
        return False
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        yi, xi = ring[i]
        yj, xj = ring[j]
        if (xi > lon) != (xj > lon):
            intersect_lat = (yj - yi) * (lon - xi) / (xj - xi) + yi
            if lat < intersect_lat:
                inside = not inside
        j = i
    return inside


def _segments_intersect(p1, p2, p3, p4) -> bool:
    """True if segment p1-p2 crosses segment p3-p4 (each point is (lat, lon))."""
    def orient(a, b, c):
        v = (b[1] - a[1]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[1] - a[1])
        return 0 if abs(v) < 1e-18 else (1 if v > 0 else -1)

    o1, o2 = orient(p1, p2, p3), orient(p1, p2, p4)
    o3, o4 = orient(p3, p4, p1), orient(p3, p4, p2)
    return o1 != o2 and o3 != o4 and 0 not in (o1, o2) and 0 not in (o3, o4)


def segment_crosses_polygon(a_lat, a_lon, b_lat, b_lon, polygon: list) -> bool:
    """True if the throw line a→b enters the hazard: either endpoint inside,
    or the segment crosses any polygon edge."""
    if len(polygon) < 3:
        return False
    if point_in_polygon(a_lat, a_lon, polygon) or point_in_polygon(b_lat, b_lon, polygon):
        return True
    n = len(polygon)
    for i in range(n):
        p3 = (polygon[i][0], polygon[i][1])
        p4 = (polygon[(i + 1) % n][0], polygon[(i + 1) % n][1])
        if _segments_intersect((a_lat, a_lon), (b_lat, b_lon), p3, p4):
            return True
    return False
