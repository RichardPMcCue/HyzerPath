import math
from typing import Optional
from app.schemas import DiscType

def map_discit_category(category: str) -> Optional[DiscType]:
    mapping = {
        "Distance Driver": DiscType.distance_driver,
        "Hybrid Driver": DiscType.fairway_driver,
        "Control Driver": DiscType.fairway_driver,
        "Midrange": DiscType.midrange,
        "Putter": DiscType.putter
    }
    return mapping.get(category)

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