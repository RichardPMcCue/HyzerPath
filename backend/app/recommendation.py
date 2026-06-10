import math
from pydantic import BaseModel
from typing import Optional

from app.utils import (
    haversine_feet,
    bearing_between,
    angle_diff,
    point_to_segment_distance,
    segment_crosses_polygon,
)

# Tuning constants
HEADWIND_FT_PER_MPH = 3.0      # distance lost per mph of headwind
TAILWIND_FT_PER_MPH = 1.5      # distance gained per mph of tailwind
CROSSWIND_DRIFT_DEG_PER_MPH = 1.5  # lateral finish shift per mph of crosswind
SHAPE_THRESHOLD_DEG = 12.0     # bend angle before a shot stops being "straight"
BIG_SHAPE_THRESHOLD_DEG = 40.0
REACH_TOLERANCE_FT = 10.0      # how short a disc can fall and still "cover" a segment

MODE_FACTORS = {
    "conservative": 0.9,
    "balanced": 1.0,
    "aggressive": 1.0,  # aggressive uses max_distance instead of avg
}

PUTT_RANGE_FT = 40.0       # ~C1: just putt the damn thing
DRIVE_FRACTION = 0.8       # segments near full reach are drives

# How far a skip-ahead throw line may stray from the mapped fairway waypoints
# before the jump is disallowed. Send-it mode may cut any corner; safe mode
# basically has to follow the corridor.
CORRIDOR_DEVIATION_FT = {
    "conservative": 35.0,
    "balanced": 80.0,
    "aggressive": float("inf"),
}

# Placement and approach shots reward control: penalize disc speed since the
# goal is landing close (C1), not covering distance.
CONTROL_PENALTY = {
    "drive": 0.0,
    "placement": 0.06,
    "approach": 0.12,
    "putt": 0.3,
}


def classify_throw(distance: float, is_final: bool, reach: float) -> str:
    """What job does this throw have? Final throws are putts (inside C1-ish)
    or approaches; earlier throws are drives or placement shots."""
    if is_final:
        return "putt" if distance <= PUTT_RANGE_FT else "approach"
    if reach and distance >= DRIVE_FRACTION * reach:
        return "drive"
    return "placement"


class SegmentRecommendation(BaseModel):
    disc: str
    disc_id: Optional[int] = None
    distance: int
    effective_distance: int
    shot_shape: str
    throw_style: str = "backhand"  # backhand | forehand
    throw_type: str = "drive"  # drive | placement | approach | putt
    from_node_id: int
    to_node_id: int
    hazards: list[str]
    skipped_node_ids: list[int] = []


def style_finishes_left(hand: str, style: str) -> bool:
    """Which way the disc fades at the end of its flight: RHBH and LHFH finish
    left; RHFH and LHBH finish right."""
    return (hand == "right") == (style == "backhand")


def wind_direction_to_degrees(direction) -> Optional[float]:
    """Accepts a compass string ("N", "SSW") or numeric degrees. Meteorological:
    the direction the wind is blowing FROM."""
    if direction is None:
        return None
    if isinstance(direction, (int, float)):
        return float(direction) % 360.0
    compass = {
        "N": 0, "NNE": 22.5, "NE": 45, "ENE": 67.5,
        "E": 90, "ESE": 112.5, "SE": 135, "SSE": 157.5,
        "S": 180, "SSW": 202.5, "SW": 225, "WSW": 247.5,
        "W": 270, "WNW": 292.5, "NW": 315, "NNW": 337.5,
    }
    return compass.get(str(direction).strip().upper())


def wind_components(wind_speed: float, wind_from_deg: Optional[float], throw_bearing: Optional[float]) -> tuple[float, float]:
    """Returns (headwind, crosswind) in mph relative to the throw.
    headwind > 0 means wind opposing the throw.
    crosswind > 0 means wind coming from the thrower's right (pushes the disc left)."""
    if not wind_speed or wind_from_deg is None or throw_bearing is None:
        return 0.0, 0.0
    rel = math.radians(angle_diff(wind_from_deg, throw_bearing))
    return wind_speed * math.cos(rel), wind_speed * math.sin(rel)


def effective_throw_distance(base_distance: float, headwind: float) -> float:
    """Wind-adjusted carry for a throw."""
    if headwind >= 0:
        return base_distance - HEADWIND_FT_PER_MPH * headwind
    return base_distance - TAILWIND_FT_PER_MPH * headwind  # headwind negative -> adds


def derive_shot_shape(finish_deg: float) -> str:
    """Maps the required finish angle (degrees; negative = finishing left for the
    target corridor) to a shot shape for a RHBH thrower."""
    if finish_deg <= -BIG_SHAPE_THRESHOLD_DEG:
        return "spike_hyzer"
    if finish_deg <= -SHAPE_THRESHOLD_DEG:
        return "hyzer"
    if finish_deg >= BIG_SHAPE_THRESHOLD_DEG:
        return "flex"
    if finish_deg >= SHAPE_THRESHOLD_DEG:
        return "anhyzer"
    return "straight"


def disc_net_stability(disc) -> float:
    """Net finish tendency. Positive = finishes left (RHBH): fade pulls left,
    turn (negative number) pushes right."""
    fade = disc.fade if disc.fade is not None else 0.0
    turn = disc.turn if disc.turn is not None else 0.0
    return fade + turn


def score_disc(disc, base_distance: float, required_distance: float, desired_stability: float, throw_type: str = "drive") -> float:
    """Higher is better. Balances distance fit, flight shape fit, and control:
    placement/approach shots prefer slow, accurate discs over drivers."""
    distance_score = -abs(base_distance - required_distance) / 25.0
    flight_score = -abs(disc_net_stability(disc) - desired_stability)
    speed = disc.speed if disc.speed is not None else 9.0
    control_score = -speed * CONTROL_PENALTY.get(throw_type, 0.0)
    return distance_score + flight_score + control_score


def _node_has_gps(node) -> bool:
    return node is not None and node.latitude is not None and node.longitude is not None


def _segment_distance(path_nodes: list, i: int, j: int, edge_lookup: dict) -> Optional[float]:
    """Distance from path node i to path node j: direct edge if one exists,
    straight-line GPS if both have coords, else cumulative edge distance."""
    direct = edge_lookup.get((path_nodes[i].hole_node_id, path_nodes[j].hole_node_id))
    if direct is not None:
        return float(direct.distance)
    a, b = path_nodes[i], path_nodes[j]
    if _node_has_gps(a) and _node_has_gps(b):
        return haversine_feet(a.latitude, a.longitude, b.latitude, b.longitude)
    total = 0.0
    for k in range(i, j):
        edge = edge_lookup.get((path_nodes[k].hole_node_id, path_nodes[k + 1].hole_node_id))
        if edge is None:
            return None
        total += edge.distance
    return total


def _hazards_between(path_nodes: list, i: int, j: int, edge_lookup: dict) -> list[str]:
    """Union of hazards on the underlying edges between path indices i and j."""
    direct = edge_lookup.get((path_nodes[i].hole_node_id, path_nodes[j].hole_node_id))
    if direct is not None and j == i + 1:
        return [h.hazard_type for h in direct.edge_hazards]
    hazards = []
    for k in range(i, j):
        edge = edge_lookup.get((path_nodes[k].hole_node_id, path_nodes[k + 1].hole_node_id))
        if edge is not None:
            hazards.extend(h.hazard_type for h in edge.edge_hazards)
    return list(dict.fromkeys(hazards))


def player_reach(discs: list, disc_distances: dict, disc_max_distances: dict, mode: str) -> float:
    """The longest single throw the engine will plan around, per mode."""
    if not discs:
        return 0.0
    disc_max_distances = disc_max_distances or {}
    best_avg = max((disc_distances.get(d.disc_id, 0) or 0) for d in discs)
    if mode == "aggressive":
        best_max = max((disc_max_distances.get(d.disc_id, 0) or 0) for d in discs)
        return float(max(best_max, best_avg))
    return best_avg * MODE_FACTORS.get(mode, 1.0)


def flatten_style_distances(style_distances: dict) -> dict:
    """Collapse {style: {disc_id: dist}} to {disc_id: best dist across styles}."""
    flat: dict = {}
    for distances in style_distances.values():
        for disc_id, dist in distances.items():
            if dist and dist > (flat.get(disc_id) or 0):
                flat[disc_id] = dist
    return flat


def _jump_corridor_deviation(path_nodes: list, i: int, j: int) -> Optional[float]:
    """How far the straight line i→j strays from the skipped fairway waypoints
    (max point-to-line distance, feet). None if GPS is missing."""
    a, b = path_nodes[i], path_nodes[j]
    if not _node_has_gps(a) or not _node_has_gps(b):
        return None
    deviation = 0.0
    for k in range(i + 1, j):
        n = path_nodes[k]
        if _node_has_gps(n):
            deviation = max(deviation, point_to_segment_distance(
                n.latitude, n.longitude,
                a.latitude, a.longitude,
                b.latitude, b.longitude,
            ))
    return deviation


def _jump_crosses_hazard(path_nodes: list, i: int, j: int, hazard_polygons: list) -> list[str]:
    """Hazard types whose polygon the straight throw line i→j enters."""
    a, b = path_nodes[i], path_nodes[j]
    if not _node_has_gps(a) or not _node_has_gps(b) or not hazard_polygons:
        return []
    return [
        hazard_type for hazard_type, polygon in hazard_polygons
        if segment_crosses_polygon(a.latitude, a.longitude, b.latitude, b.longitude, polygon)
    ]


def plan_segments(
    path_nodes: list,
    edge_lookup: dict,
    reach_limit: float,
    mode: str,
    wind_speed: float = 0.0,
    wind_from_deg: Optional[float] = None,
    hazard_polygons: Optional[list] = None,  # [(hazard_type, [[lat, lng], ...])]
) -> list[tuple[int, int]]:
    """Lookahead/pruning: walk the Dijkstra path and greedily jump to the furthest
    node reachable in one throw (wind-adjusted). Returns (from_index, to_index) pairs.

    conservative: follows the corridor (≤35 ft cut), never crosses hazards
    balanced: small corner cuts (≤80 ft), never crosses hazards, 95% of reach
    aggressive: cuts anything within reach, hazards be damned"""
    hazard_polygons = hazard_polygons or []
    segments = []
    i = 0
    last = len(path_nodes) - 1
    while i < last:
        best_j = i + 1
        for j in range(last, i + 1, -1):
            if j == i + 1:
                break
            dist = _segment_distance(path_nodes, i, j, edge_lookup)
            if dist is None:
                continue
            # Wind-adjust the player's reach for this jump's bearing
            limit = reach_limit
            if _node_has_gps(path_nodes[i]) and _node_has_gps(path_nodes[j]):
                jump_bearing = bearing_between(
                    path_nodes[i].latitude, path_nodes[i].longitude,
                    path_nodes[j].latitude, path_nodes[j].longitude,
                )
                headwind, _ = wind_components(wind_speed, wind_from_deg, jump_bearing)
                limit = effective_throw_distance(reach_limit, headwind)
            if mode == "balanced":
                limit *= 0.95
            if dist > limit:
                continue
            # The jump is a straight throw: it must respect the mapped fairway
            # (per-mode corner-cut tolerance) and not fly through drawn hazards
            deviation = _jump_corridor_deviation(path_nodes, i, j)
            if deviation is not None and deviation > CORRIDOR_DEVIATION_FT.get(mode, 80.0):
                continue
            if mode != "aggressive" and _jump_crosses_hazard(path_nodes, i, j, hazard_polygons):
                continue
            if mode == "conservative" and _hazards_between(path_nodes, i, j, edge_lookup):
                continue
            best_j = j
            break
        segments.append((i, best_j))
        i = best_j
    return segments


def recommend_path(
    path_nodes: list,
    edge_lookup: dict,  # {(from_node_id, to_node_id): HoleEdge}
    discs: list,
    disc_distances: dict,  # {disc_id: avg_distance} — best across styles
    disc_max_distances: Optional[dict] = None,  # {disc_id: max_distance}
    wind_speed: float = 0.0,
    wind_direction=None,  # compass string or degrees, wind FROM
    mode: str = "balanced",
    style_distances: Optional[dict] = None,  # {style: {disc_id: avg_distance}}
    hand: str = "right",
    style_priority: Optional[dict] = None,  # {style: 1-based priority, 1 = primary}
    hazard_polygons: Optional[list] = None,  # [(hazard_type, [[lat, lng], ...])]
) -> list[SegmentRecommendation]:
    if len(path_nodes) < 2 or not discs:
        return []

    disc_max_distances = disc_max_distances or {}
    # Without per-style data, everything counts as backhand (legacy behavior)
    if not style_distances:
        style_distances = {"backhand": disc_distances}
    style_priority = style_priority or {}
    # Only consider styles the player actually has distance data for
    styles = [s for s, d in style_distances.items() if any(v for v in d.values())]
    if not styles:
        styles = ["backhand"]
        style_distances = {"backhand": disc_distances}

    wind_from_deg = wind_direction_to_degrees(wind_direction)
    reach_limit = player_reach(discs, disc_distances, disc_max_distances, mode)

    segments = plan_segments(
        path_nodes, edge_lookup, reach_limit, mode, wind_speed, wind_from_deg, hazard_polygons
    )
    recommendations = []

    for seg_idx, (i, j) in enumerate(segments):
        from_node, to_node = path_nodes[i], path_nodes[j]
        distance = _segment_distance(path_nodes, i, j, edge_lookup) or 0.0

        # Throw bearing for wind and shape math
        throw_bearing = None
        if _node_has_gps(from_node) and _node_has_gps(to_node):
            throw_bearing = bearing_between(
                from_node.latitude, from_node.longitude,
                to_node.latitude, to_node.longitude,
            )

        # Finish angle: how the corridor bends at the landing node. The throw
        # should finish pointing down the next segment.
        finish_deg = 0.0
        if seg_idx + 1 < len(segments):
            _, next_j = segments[seg_idx + 1]
            next_node = path_nodes[next_j]
            if throw_bearing is not None and _node_has_gps(next_node):
                next_bearing = bearing_between(
                    to_node.latitude, to_node.longitude,
                    next_node.latitude, next_node.longitude,
                )
                finish_deg = angle_diff(next_bearing, throw_bearing)

        # Wind: headwind shortens the throw, crosswind shifts the finish
        headwind, crosswind = wind_components(wind_speed, wind_from_deg, throw_bearing)
        finish_deg_adjusted = finish_deg + CROSSWIND_DRIFT_DEG_PER_MPH * crosswind

        throw_type = classify_throw(distance, is_final=(seg_idx == len(segments) - 1), reach=reach_limit)

        # Evaluate every (style, disc) pair: forehand mirrors the shape math, so
        # a dogleg that needs a flex backhand is a simple hyzer forehand. Use the
        # player's measured distances for that style.
        best = None  # (score, disc, style, shot_shape)
        for style in styles:
            distances = style_distances.get(style, {})
            if not any(distances.values()):
                continue

            # Normalize the finish angle to this style's fade direction:
            # negative = "hyzer side" regardless of hand/style
            normalized = finish_deg_adjusted if style_finishes_left(hand, style) else -finish_deg_adjusted
            shot_shape_s = derive_shot_shape(normalized)
            desired_stability = max(-3.0, min(4.0, -normalized / 15.0))

            def carry(d, _distances=distances):
                base = _distances.get(d.disc_id, 0) or 0
                return effective_throw_distance(base, headwind)

            with_data = [d for d in discs if distances.get(d.disc_id)]
            if not with_data:
                continue
            capable = [d for d in with_data if carry(d) >= distance - REACH_TOLERANCE_FT]
            if not capable:
                capable = [max(with_data, key=carry)]

            # Primary style wins ties; big shapes for the off-hand cost more
            priority_penalty = 0.15 * (style_priority.get(style, 1) - 1)
            for d in capable:
                score = score_disc(d, carry(d), distance, desired_stability, throw_type) - priority_penalty
                if best is None or score > best[0]:
                    best = (score, d, style, shot_shape_s)

        if best is None:
            continue
        _, best_disc, best_style, shot_shape = best

        recommendations.append(SegmentRecommendation(
            disc=f"{best_disc.manufacturer} {best_disc.name}",
            disc_id=best_disc.disc_id,
            distance=round(distance),
            effective_distance=round(distance + (HEADWIND_FT_PER_MPH * headwind if headwind > 0 else TAILWIND_FT_PER_MPH * headwind)),
            shot_shape=shot_shape,
            throw_style=best_style,
            throw_type=throw_type,
            from_node_id=from_node.hole_node_id,
            to_node_id=to_node.hole_node_id,
            # Edge-tagged hazards plus any polygons the actual throw line enters
            # (a send-it corner cut earns its ⚠ even when the path edges are clean)
            hazards=list(dict.fromkeys(
                _hazards_between(path_nodes, i, j, edge_lookup)
                + _jump_crosses_hazard(path_nodes, i, j, hazard_polygons or [])
            )),
            skipped_node_ids=[path_nodes[k].hole_node_id for k in range(i + 1, j)],
        ))

    return recommendations
