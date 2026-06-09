import math
from pydantic import BaseModel
from typing import Optional

from app.utils import haversine_feet, bearing_between, angle_diff

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
    throw_type: str = "drive"  # drive | placement | approach | putt
    from_node_id: int
    to_node_id: int
    hazards: list[str]
    skipped_node_ids: list[int] = []


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


def plan_segments(
    path_nodes: list,
    edge_lookup: dict,
    reach_limit: float,
    mode: str,
    wind_speed: float = 0.0,
    wind_from_deg: Optional[float] = None,
) -> list[tuple[int, int]]:
    """Lookahead/pruning: walk the Dijkstra path and greedily jump to the furthest
    node reachable in one throw (wind-adjusted). Returns (from_index, to_index) pairs.

    conservative: never skips past an edge with hazards
    balanced: skips, but only well within reach (95% of limit)
    aggressive: skips anything within reach"""
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
    disc_distances: dict,  # {disc_id: avg_distance}
    disc_max_distances: Optional[dict] = None,  # {disc_id: max_distance}
    wind_speed: float = 0.0,
    wind_direction=None,  # compass string or degrees, wind FROM
    mode: str = "balanced",
) -> list[SegmentRecommendation]:
    if len(path_nodes) < 2 or not discs:
        return []

    disc_max_distances = disc_max_distances or {}
    wind_from_deg = wind_direction_to_degrees(wind_direction)
    reach_limit = player_reach(discs, disc_distances, disc_max_distances, mode)

    segments = plan_segments(path_nodes, edge_lookup, reach_limit, mode, wind_speed, wind_from_deg)
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

        shot_shape = derive_shot_shape(finish_deg_adjusted)
        # Desired net stability: a left finish (negative deg) wants fade
        desired_stability = max(-3.0, min(4.0, -finish_deg_adjusted / 15.0))

        throw_type = classify_throw(distance, is_final=(seg_idx == len(segments) - 1), reach=reach_limit)

        # Filter discs whose wind-adjusted carry covers the segment
        def carry(d):
            base = disc_distances.get(d.disc_id, 0) or 0
            return effective_throw_distance(base, headwind)

        capable = [d for d in discs if carry(d) >= distance - REACH_TOLERANCE_FT]
        if not capable:
            capable = [max(discs, key=carry)]

        best_disc = max(
            capable,
            key=lambda d: score_disc(d, carry(d), distance, desired_stability, throw_type),
        )

        recommendations.append(SegmentRecommendation(
            disc=f"{best_disc.manufacturer} {best_disc.name}",
            disc_id=best_disc.disc_id,
            distance=round(distance),
            effective_distance=round(distance + (HEADWIND_FT_PER_MPH * headwind if headwind > 0 else TAILWIND_FT_PER_MPH * headwind)),
            shot_shape=shot_shape,
            throw_type=throw_type,
            from_node_id=from_node.hole_node_id,
            to_node_id=to_node.hole_node_id,
            hazards=_hazards_between(path_nodes, i, j, edge_lookup),
            skipped_node_ids=[path_nodes[k].hole_node_id for k in range(i + 1, j)],
        ))

    return recommendations
