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


def point_to_segment_distance(
    point_lat: float, point_lon: float,
    seg_start_lat: float, seg_start_lon: float,
    seg_end_lat: float, seg_end_lon: float
) -> float:
    # Convert degrees to feet using a local projection
    lat_to_feet = 364000.0
    lon_to_feet = 364000.0 * math.cos(math.radians(point_lat))

    px = (point_lon - seg_start_lon) * lon_to_feet
    py = (point_lat - seg_start_lat) * lat_to_feet
    dx = (seg_end_lon - seg_start_lon) * lon_to_feet
    dy = (seg_end_lat - seg_start_lat) * lat_to_feet

    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq == 0:
        # Segment is a single point
        return math.sqrt(px * px + py * py)

    # Project point onto segment, clamped to [0, 1]
    t = max(0.0, min(1.0, (px * dx + py * dy) / seg_len_sq))

    closest_x = t * dx - px
    closest_y = t * dy - py
    return math.sqrt(closest_x * closest_x + closest_y * closest_y)


def compute_centerline_distance(
    node_lat: float, node_lon: float,
    centerline_points: list
) -> float:
    if len(centerline_points) < 2:
        return 0.0

    min_distance = float("inf")
    for i in range(len(centerline_points) - 1):
        a = centerline_points[i]
        b = centerline_points[i + 1]
        dist = point_to_segment_distance(
            node_lat, node_lon,
            a.latitude, a.longitude,
            b.latitude, b.longitude,
        )
        if dist < min_distance:
            min_distance = dist

    return min_distance

def compute_dynamic_centerline(fairway_nodes: list) -> list:
    """
    Takes a list of HoleNode objects where is_fairway=True,
    sorted by sequence. Returns ordered list of (lat, lon) tuples
    representing the estimated centerline.
    """
    sorted_nodes = sorted(
        [n for n in fairway_nodes if n.latitude and n.longitude],
        key=lambda n: n.sequence
    )
    return [(n.latitude, n.longitude) for n in sorted_nodes]


def offset_point(lat: float, lon: float, bearing_deg: float, dist_ft: float) -> tuple:
    """Moves a lat/lon point dist_ft feet along a compass bearing."""
    b = math.radians(bearing_deg)
    dlat = dist_ft * math.cos(b) / 364000.0
    dlon = dist_ft * math.sin(b) / (364000.0 * math.cos(math.radians(lat)))
    return (lat + dlat, lon + dlon)


def compute_fairway_polygon(fairway_nodes: list, edges: list, default_width: float = 30.0) -> list:
    """Buffers the fairway centerline into a corridor polygon for map display.

    Walks the fairway nodes in sequence, offsetting each centerline point
    perpendicular to the local direction by half the fairway width (taken from
    the adjacent edges, falling back to default_width). Returns a closed ring
    of (lat, lon) tuples, or [] if there aren't enough located nodes."""
    pts = sorted(
        [n for n in fairway_nodes if n.latitude is not None and n.longitude is not None],
        key=lambda n: n.sequence,
    )
    if len(pts) < 2:
        return []

    width_by_pair = {}
    for e in edges:
        if e.fairway_width:
            width_by_pair[(e.from_node_id, e.to_node_id)] = float(e.fairway_width)
            width_by_pair[(e.to_node_id, e.from_node_id)] = float(e.fairway_width)

    bearing = lambda a, b: bearing_between(a.latitude, a.longitude, b.latitude, b.longitude)

    left, right = [], []
    for i, p in enumerate(pts):
        # Local direction: average of adjacent segment bearings (vector mean)
        vx = vy = 0.0
        if i > 0:
            b = math.radians(bearing(pts[i - 1], p))
            vx += math.sin(b); vy += math.cos(b)
        if i < len(pts) - 1:
            b = math.radians(bearing(p, pts[i + 1]))
            vx += math.sin(b); vy += math.cos(b)
        direction = math.degrees(math.atan2(vx, vy)) % 360.0

        widths = []
        if i > 0:
            w = width_by_pair.get((pts[i - 1].hole_node_id, p.hole_node_id))
            if w: widths.append(w)
        if i < len(pts) - 1:
            w = width_by_pair.get((p.hole_node_id, pts[i + 1].hole_node_id))
            if w: widths.append(w)
        half = (sum(widths) / len(widths) if widths else default_width) / 2.0

        left.append(offset_point(p.latitude, p.longitude, direction - 90.0, half))
        right.append(offset_point(p.latitude, p.longitude, direction + 90.0, half))

    ring = left + right[::-1]
    ring.append(ring[0])
    return ring


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


def compute_fairway_width_at_sequence(fairway_nodes: list, sequence: int) -> Optional[float]:
    """
    Estimates fairway width at a given sequence point by finding
    nodes at the same sequence and measuring their spread.
    Falls back to neighbors if not enough nodes at exact sequence.
    """
    nearby = [n for n in fairway_nodes 
              if abs(n.sequence - sequence) <= 1 
              and n.latitude and n.longitude]
    
    if len(nearby) < 2:
        return None
    
    lats = [n.latitude for n in nearby]
    lons = [n.longitude for n in nearby]
    
    lat_spread = (max(lats) - min(lats)) * 364000
    lon_spread = (max(lons) - min(lons)) * 297000
    
    return max(lat_spread, lon_spread)

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


FAIRWAY_FIT_TOLERANCE_FT = 40.0
SMOOTHING_MIN_POINTS = 6  # keep in sync with frontend geo.ts


def smooth_chain(points: list) -> list:
    """Single-pass weighted moving average (0.25 prev / 0.5 self / 0.25 next)
    on interior points; endpoints fixed. Corridor-outline taps zigzag laterally
    and average out to the centerline. Skipped for sparse chains
    (< SMOOTHING_MIN_POINTS) so deliberately placed dogleg corners survive."""
    if len(points) < SMOOTHING_MIN_POINTS:
        return list(points)
    out = [points[0]]
    for i in range(1, len(points) - 1):
        p, c, n = points[i - 1], points[i], points[i + 1]
        out.append((
            0.25 * p[0] + 0.5 * c[0] + 0.25 * n[0],
            0.25 * p[1] + 0.5 * c[1] + 0.25 * n[1],
        ))
    out.append(points[-1])
    return out


def simplify_path(points: list, tolerance_ft: float = FAIRWAY_FIT_TOLERANCE_FT) -> list:
    """Douglas-Peucker on a chain of (lat, lng) points: drops points within
    tolerance of the line so played distance follows the best-fit fairway line,
    not every lateral waypoint tap. Real dogleg corners survive."""
    if len(points) < 3:
        return list(points)
    a, b = points[0], points[-1]
    max_idx, max_dev = 0, 0.0
    for i in range(1, len(points) - 1):
        dev = point_to_segment_distance(points[i][0], points[i][1], a[0], a[1], b[0], b[1])
        if dev > max_dev:
            max_idx, max_dev = i, dev
    if max_dev <= tolerance_ft:
        return [a, b]
    left = simplify_path(points[:max_idx + 1], tolerance_ft)
    right = simplify_path(points[max_idx:], tolerance_ft)
    return left[:-1] + right


def path_distance_feet(points: list, tolerance_ft: float = FAIRWAY_FIT_TOLERANCE_FT) -> float:
    """Length of the best-fit line through a chain of (lat, lng) points."""
    simplified = simplify_path(smooth_chain(points), tolerance_ft)
    return sum(
        haversine_feet(a[0], a[1], b[0], b[1])
        for a, b in zip(simplified, simplified[1:])
    )


def fairway_chain_to_basket(points: list) -> list:
    """Drop waypoints that sit past the basket so a node placed beyond the pin
    doesn't inflate the hole's played length. `points` is [(lat, lng), ...] with
    the tee first and basket last; a point counts only if its projection onto
    the tee->basket axis lands at or before the basket (t <= 1)."""
    if len(points) < 3:
        return points
    tee, basket = points[0], points[-1]
    lon_ft = 364000.0 * math.cos(math.radians(tee[0]))
    def vec(a, b):
        return ((b[1] - a[1]) * lon_ft, (b[0] - a[0]) * 364000.0)
    ax, ay = vec(tee, basket)          # tee -> basket axis
    axis2 = ax * ax + ay * ay
    if axis2 == 0:
        return points
    kept = [tee]
    for p in points[1:-1]:
        nx, ny = vec(tee, p)
        if (nx * ax + ny * ay) / axis2 <= 1.0:  # 0 at tee, 1 at basket
            kept.append(p)
    kept.append(basket)
    return kept


def _demo():
    LAT = 1 / 364000.0
    tee = (0.0, 0.0)
    basket = (300 * LAT, 0.0)
    # An overshoot node 100ft past the basket must not lengthen the hole — the
    # straight tee->basket distance is ~300ft, not the 500ft out-and-back.
    overshoot = (400 * LAT, 0.0)
    assert path_distance_feet(fairway_chain_to_basket([tee, overshoot, basket])) < 320
    # A real dogleg corner (lateral, before the basket) is kept and adds length.
    corner = (150 * LAT, 150 * LAT)
    assert path_distance_feet(fairway_chain_to_basket([tee, corner, basket])) > 380
    print("ok")


if __name__ == "__main__":
    _demo()
