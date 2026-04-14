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