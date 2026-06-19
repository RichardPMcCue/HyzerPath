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

PUTT_RANGE_FT = 66.0       # inside C2: putt or jump putt, not an "approach"
DRIVE_FRACTION = 0.8       # segments near full reach are drives

# Putting circles, measured from the basket (feet)
C1_FT = 33.0   # Circle 1: ~10 m, a makeable par/birdie putt
C2_FT = 66.0   # Circle 2: ~20 m
C3_FT = 100.0  # Circle 3: a long look

# Fairway tightness from corridor width: at/under TIGHT a tunnel (1.0),
# at/over OPEN there's room to work the disc (0.0), linear in between.
TIGHT_WIDTH_FT = 25.0
OPEN_WIDTH_FT = 70.0
# A "trees" hazard polygon this close to the throw line tightens the corridor.
TREE_PROXIMITY_FT = 30.0

# score_disc tightness penalty: how much lateral movement and forced max-effort
# cost on a fully-tight fairway (scaled by tightness and mode).
W_LAT = 0.5      # per unit of |turn| + fade, on a fully-tight fairway
W_EFFORT = 3.0   # per unit of avg→max reach on a tight fairway (added lateral movement)
BASE_EFFORT_PENALTY = 0.8  # max-effort throws are less reliable, even in the open
OVER_DISC_FT = 45.0  # "too much club": cost per foot the disc's avg overshoots the target

# How much each mode cares about tunnel control. Aggressive players accept the
# lateral spread of a max-effort line; conservative players avoid it.
MODE_TIGHTNESS_SCALE = {
    "conservative": 1.3,
    "balanced": 1.0,
    "aggressive": 0.4,
}

# How far a skip-ahead throw line may stray from the mapped fairway waypoints
# before the jump is disallowed. Send-it mode may cut any corner; safe mode
# basically has to follow the corridor.
CORRIDOR_DEVIATION_FT = {
    "conservative": 70.0,
    "balanced": 110.0,
    "aggressive": float("inf"),
}

# A spike hyzer is a short, steep touch shot — never a long drive. Above this
# distance a big finishing bend is a regular (sweeping) hyzer, not a spike.
SPIKE_MAX_FT = 250.0

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
    landing_zone: str = "fairway"  # fairway | c1 | c2 | c3 | basket
    rationale: str = ""
    # Flight numbers of the recommended disc, so two copies of the same mold at
    # different wear can be told apart on the card.
    speed: Optional[float] = None
    glide: Optional[float] = None
    turn: Optional[float] = None
    fade: Optional[float] = None
    wear: Optional[float] = None
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


def derive_shot_shape(finish_deg: float, disc=None, effort: float = 0.0, distance: float = 0.0) -> str:
    """Maps the required finish angle plus the chosen disc's stability to a shot
    shape. finish_deg is normalized so negative = the thrower's hyzer (fade) side
    and positive = the anhyzer (turn) side, which keeps forehand / left-handed
    throws mirrored correctly. `effort` is how hard the disc is being reached
    toward its max line (0 = controlled, 1 = max-effort).

    The disc matters: a right-bending corridor is a flex with an overstable disc
    (turns then fights back) but a turnover with an understable one; a straight
    corridor reached with an understable disc is a hyzer flip."""
    net = disc_net_stability(disc) if disc is not None else 0.0

    # Left / hyzer side. A sharp finish is a spike hyzer only on a short touch
    # shot; on a drive that same bend is just a big sweeping hyzer.
    if finish_deg <= -BIG_SHAPE_THRESHOLD_DEG:
        return "spike_hyzer" if distance <= SPIKE_MAX_FT else "hyzer"
    if finish_deg <= -SHAPE_THRESHOLD_DEG:
        return "hyzer"

    # Right / anhyzer side
    if finish_deg >= SHAPE_THRESHOLD_DEG:
        if net >= 1.0:
            return "flex"  # overstable disc on an anhyzer line, flexes back
        return "turnover" if finish_deg >= BIG_SHAPE_THRESHOLD_DEG else "anhyzer"

    # Roughly straight corridor: an understable disc thrown to reach flips up and
    # rides — the distance-efficient line, and the way to hold a straight tunnel.
    if net <= -1.0 and effort > 0.2:
        return "hyzer_flip"
    return "straight"


def lateral_movement(disc) -> float:
    """How far the disc works off a straight line: |turn| + fade. Higher = more
    side-to-side travel, harder to keep inside a tight corridor."""
    fade = disc.fade if getattr(disc, "fade", None) is not None else 0.0
    turn = disc.turn if getattr(disc, "turn", None) is not None else 0.0
    return abs(turn) + fade


def throw_effort(required: float, avg: float, max_distance: float) -> float:
    """How hard the player must reach to cover `required` with this disc.

    avg = the controlled, repeatable line (0 effort); max = a max-effort line
    that already bakes in big anhyzer / flex / hyzer-flip lateral movement (1.0).
    Beyond max returns >1 (the disc can't realistically cover it). This is what
    lets a slower disc the player controls beat a faster one they'd have to
    muscle to the same distance on a tight fairway."""
    avg = avg or 0.0
    if required <= avg:
        return 0.0
    max_distance = max_distance or avg
    if max_distance <= avg:
        return 1.0  # no measured spread: anything past avg is full effort
    return (required - avg) / (max_distance - avg)


def fairway_tightness(width, throw_line, tree_polygons) -> float:
    """Corridor tightness in [0, 1] from the fairway width and nearby mapped
    trees. throw_line is (lat1, lon1, lat2, lon2) or None; tree_polygons is a
    list of [[lat, lng], ...] rings."""
    width_term = 0.0
    if width:
        width_term = (OPEN_WIDTH_FT - width) / (OPEN_WIDTH_FT - TIGHT_WIDTH_FT)
        width_term = max(0.0, min(1.0, width_term))

    tree_term = 0.0
    if throw_line is not None and tree_polygons:
        lat1, lon1, lat2, lon2 = throw_line
        nearest = None
        for polygon in tree_polygons:
            for point in polygon:
                d = point_to_segment_distance(point[0], point[1], lat1, lon1, lat2, lon2)
                if nearest is None or d < nearest:
                    nearest = d
        if nearest is not None and nearest < TREE_PROXIMITY_FT:
            tree_term = 1.0 - nearest / TREE_PROXIMITY_FT

    return max(width_term, tree_term)


def landing_zone_for(distance: float, throw_type: str, is_final: bool, mode: str) -> str:
    """Intended landing zone for a throw. Earlier throws place on the fairway;
    the final throw's target circle is set by the risk mode (safe leaves a putt,
    aggressive goes at the basket)."""
    if not is_final:
        return "fairway"
    if throw_type == "putt":
        return "c1" if distance <= C1_FT else "c2"
    # Final approach (>C2): how close we intend to get depends on the mode.
    if mode == "aggressive":
        return "c1"
    return "c2"  # balanced / conservative lay up to a safe par putt


def tightness_label(tightness: float) -> str:
    if tightness >= 0.66:
        return "tight tunnel"
    if tightness >= 0.33:
        return "wooded"
    return "open"


def _fmt_flight(value) -> str:
    if value is None:
        return "–"
    return f"{value:g}"


def build_rationale(disc, shape: str, tightness: float, distance: float, effort: float) -> str:
    """One-line, human explanation referencing the disc's flight numbers and the
    fairway, e.g. 'DD3 (12/6/-1/2): controlled flat line on a tight tunnel, 420 ft.'"""
    nums = "/".join(_fmt_flight(getattr(disc, k, None)) for k in ("speed", "glide", "turn", "fade"))
    name = getattr(disc, "name", None) or "disc"
    shape_label = shape.replace("_", " ")
    reach = "near its max line" if effort > 0.66 else ("controlled line" if effort < 0.34 else "comfortable line")
    label = tightness_label(tightness)
    article = "an" if label[0] in "aeiou" else "a"
    return f"{name} ({nums}): {shape_label} on {article} {label} fairway, {reach} for {round(distance)} ft."


def disc_net_stability(disc) -> float:
    """Net finish tendency. Positive = finishes left (RHBH): fade pulls left,
    turn (negative number) pushes right."""
    fade = disc.fade if disc.fade is not None else 0.0
    turn = disc.turn if disc.turn is not None else 0.0
    return fade + turn


def score_disc(disc, base_distance: float, required_distance: float, desired_stability: float,
               throw_type: str = "drive", tightness: float = 0.0, effort: float = 0.0,
               mode: str = "balanced") -> float:
    """Higher is better. Each disc covers a range from its avg (controlled) up to
    its max line; the target is reachable when it's within that range. Scoring
    balances:
      - too-much-club: a disc whose avg overshoots the target is harder to throw
        accurately at the shorter distance;
      - effort: reaching from avg toward max is less reliable (always) and adds
        lateral movement that hurts on tight fairways (not in the open);
      - flight-shape fit and control (placement/approach want slow, accurate discs)."""
    over_disc = max(0.0, base_distance - required_distance)
    distance_score = -over_disc / OVER_DISC_FT
    flight_score = -abs(disc_net_stability(disc) - desired_stability)
    speed = disc.speed if disc.speed is not None else 9.0
    control_score = -speed * CONTROL_PENALTY.get(throw_type, 0.0)
    tight_scale = MODE_TIGHTNESS_SCALE.get(mode, 1.0)
    effort_score = -(BASE_EFFORT_PENALTY + tight_scale * W_EFFORT * tightness) * effort
    lateral_score = -tight_scale * W_LAT * tightness * lateral_movement(disc)
    return distance_score + flight_score + control_score + effort_score + lateral_score


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


def _segment_width(path_nodes: list, i: int, j: int, fairway_widths: dict) -> Optional[float]:
    """Corridor width for a (possibly skip-ahead) throw i→j. The tightest of the
    underlying edges governs, since the throw has to fit through all of them."""
    widths = []
    direct = fairway_widths.get((path_nodes[i].hole_node_id, path_nodes[j].hole_node_id))
    if direct:
        widths.append(direct)
    for k in range(i, j):
        w = fairway_widths.get((path_nodes[k].hole_node_id, path_nodes[k + 1].hole_node_id))
        if w:
            widths.append(w)
    return min(widths) if widths else None


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
    style_max_distances: Optional[dict] = None,  # {style: {disc_id: max_distance}}
    hand: str = "right",
    style_priority: Optional[dict] = None,  # {style: 1-based priority, 1 = primary}
    hazard_polygons: Optional[list] = None,  # [(hazard_type, [[lat, lng], ...])]
    fairway_widths: Optional[dict] = None,  # {(from_node_id, to_node_id): width_ft}
    allowed_styles: Optional[list] = None,  # restrict to these styles (user profile)
    style_hands: Optional[dict] = None,  # {style: 'right'|'left'} for ambidextrous players
) -> list[SegmentRecommendation]:
    if len(path_nodes) < 2 or not discs:
        return []

    disc_max_distances = disc_max_distances or {}
    fairway_widths = fairway_widths or {}
    style_hands = style_hands or {}
    # Mapped tree areas tighten the corridor where they crowd the throw line
    tree_polygons = [poly for htype, poly in (hazard_polygons or []) if htype == "trees"]
    # Without per-style data, everything counts as backhand (legacy behavior)
    if not style_distances:
        style_distances = {"backhand": disc_distances}
    if not style_max_distances:
        style_max_distances = {"backhand": disc_max_distances}
    # No throw-style profile → assume backhand-primary: ties go to the backhand
    style_priority = style_priority or {"backhand": 1, "forehand": 2}
    # Only consider styles the player has distance data for AND has enabled
    styles = [
        s for s, d in style_distances.items()
        if any(v for v in d.values()) and (not allowed_styles or s in allowed_styles)
    ]
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

        is_final = seg_idx == len(segments) - 1
        throw_type = classify_throw(distance, is_final=is_final, reach=reach_limit)

        # Tunnel vs. open: from the corridor width (tightest underlying edge) and
        # any mapped trees crowding the throw line.
        throw_line = None
        if _node_has_gps(from_node) and _node_has_gps(to_node):
            throw_line = (from_node.latitude, from_node.longitude, to_node.latitude, to_node.longitude)
        width = _segment_width(path_nodes, i, j, fairway_widths)
        tightness = fairway_tightness(width, throw_line, tree_polygons)

        # Evaluate every (style, disc) pair: forehand mirrors the shape math, so
        # a dogleg that needs a flex backhand is a simple hyzer forehand. Use the
        # player's measured distances for that style.
        best = None  # (score, disc, style, normalized, effort)
        for style in styles:
            distances = style_distances.get(style, {})
            if not any(distances.values()):
                continue
            max_dists = style_max_distances.get(style, {}) or {}

            # Normalize the finish angle to this style's fade direction:
            # negative = "hyzer side" regardless of hand/style. Ambidextrous
            # players can have a different hand per style.
            throw_hand = style_hands.get(style, hand)
            normalized = finish_deg_adjusted if style_finishes_left(throw_hand, style) else -finish_deg_adjusted
            desired_stability = max(-3.0, min(4.0, -normalized / 15.0))

            def carry(d, _distances=distances):
                base = _distances.get(d.disc_id, 0) or 0
                return effective_throw_distance(base, headwind)

            def max_carry(d, _max=max_dists, _distances=distances):
                # The top of the disc's range; fall back to avg if no max recorded
                base = _max.get(d.disc_id) or _distances.get(d.disc_id, 0) or 0
                return effective_throw_distance(base, headwind)

            def effort_for(d, _distances=distances, _max=max_dists):
                # Effort measured against the wind-adjusted controlled and max lines
                avg = effective_throw_distance(_distances.get(d.disc_id, 0) or 0, headwind)
                dmax = effective_throw_distance(_max.get(d.disc_id, 0) or 0, headwind)
                return throw_effort(distance, avg, dmax)

            with_data = [d for d in discs if distances.get(d.disc_id)]
            if not with_data:
                continue
            # A disc is in play if the target falls within its range (up to its
            # max line), so every driver that can reach competes — not just the
            # one whose average is longest.
            capable = [d for d in with_data if max_carry(d) >= distance - REACH_TOLERANCE_FT]
            if not capable:
                capable = [max(with_data, key=max_carry)]

            # Primary style wins ties; big shapes for the off-hand cost more
            priority_penalty = 0.15 * (style_priority.get(style, 1) - 1)
            for d in capable:
                effort = effort_for(d)
                score = score_disc(
                    d, carry(d), distance, desired_stability, throw_type,
                    tightness=tightness, effort=effort, mode=mode,
                ) - priority_penalty
                if best is None or score > best[0]:
                    best = (score, d, style, normalized, effort)

        if best is None:
            continue
        _, best_disc, best_style, best_normalized, best_effort = best

        # Shape depends on the chosen disc: flex vs. turnover, hyzer flip vs. flat
        shot_shape = derive_shot_shape(best_normalized, best_disc, best_effort, distance)
        landing_zone = landing_zone_for(distance, throw_type, is_final, mode)
        rationale = build_rationale(best_disc, shot_shape, tightness, distance, best_effort)

        recommendations.append(SegmentRecommendation(
            disc=f"{best_disc.manufacturer} {best_disc.name}",
            disc_id=best_disc.disc_id,
            distance=round(distance),
            effective_distance=round(distance + (HEADWIND_FT_PER_MPH * headwind if headwind > 0 else TAILWIND_FT_PER_MPH * headwind)),
            shot_shape=shot_shape,
            throw_style=best_style,
            throw_type=throw_type,
            landing_zone=landing_zone,
            rationale=rationale,
            speed=getattr(best_disc, "speed", None),
            glide=getattr(best_disc, "glide", None),
            turn=getattr(best_disc, "turn", None),
            fade=getattr(best_disc, "fade", None),
            wear=getattr(best_disc, "wear", None),
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
