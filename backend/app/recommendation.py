import math
from pydantic import BaseModel
from typing import Optional

from app.fairway import FairwayRegion, clearance_to_tightness
from app.utils import (
    bearing_between,
    angle_diff,
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

# A disc flight can shape around a corridor bend, but not wrap a hard corner
# mid-flight: a route vertex turning more than this caps the throw there (the
# classic "place it at the corner, then attack" plan).
MAX_BEND_PER_THROW_DEG = 50.0
MIN_THROW_FT = 40.0  # never plan a shorter hop than this

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

# A line that must finish on the turn side (anhyzer/turnover family) is a
# lower-percentage release than a hyzer at equal flight fit — the throw fights
# the disc's natural finish. Applied when the corridor demands a committed
# turn-side shape (desired_stability at/under -SHAPE_THRESHOLD_DEG/15), which
# also makes the mirrored style's hyzer read comparatively cheaper.
SHAPE_RISK_PENALTY = 0.25


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
    # Where the throw starts and where it should land (derived route targets)
    start_latitude: Optional[float] = None
    start_longitude: Optional[float] = None
    target_latitude: Optional[float] = None
    target_longitude: Optional[float] = None
    is_recovery: bool = False  # lie was outside the fairway; this throw gets back in
    hazards: list[str] = []


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
    # Technique risk: a committed turn-side (anhyzer/turnover) line is a
    # lower-percentage release than a hyzer at equal fit.
    shape_risk = -SHAPE_RISK_PENALTY if desired_stability <= -(SHAPE_THRESHOLD_DEG / 15.0) else 0.0
    return distance_score + flight_score + control_score + effort_score + lateral_score + shape_risk


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


def plan_route_targets(
    region: FairwayRegion,
    route: list,  # [(lat, lng), ...] derived playing line, start first
    reach_limit: float,
    mode: str,
    wind_speed: float = 0.0,
    wind_from_deg: Optional[float] = None,
) -> list[tuple[float, float]]:
    """Walk the derived route and split it into throws: each span reaches as
    far along the route as one controlled throw allows (wind-adjusted), but
    never wraps a sharp corner mid-flight — those throws land AT the corner.
    Returns (d0, d1) distance spans along the route."""
    dists = region.cumulative_ft(route)
    total = dists[-1]

    # Sharp corners a single flight can't wrap. Turn is accumulated over a
    # short window so a corner beveled into several small bends (buffered /
    # simplified polygons) still registers as one corner.
    turns = []
    for i in range(1, len(route) - 1):
        b_in = bearing_between(*route[i - 1], *route[i])
        b_out = bearing_between(*route[i], *route[i + 1])
        turns.append((dists[i], angle_diff(b_out, b_in)))
    corners = []
    i = 0
    while i < len(turns):
        d_i, acc = turns[i]
        j = i + 1
        while j < len(turns) and turns[j][0] - d_i <= 80.0:
            acc += turns[j][1]
            j += 1
        if abs(acc) > MAX_BEND_PER_THROW_DEG:
            # cap at the window's sharpest vertex
            sharpest = max(turns[i:j], key=lambda t: abs(t[1]))
            corners.append(sharpest[0])
            i = j
        else:
            i += 1

    spans = []
    d = 0.0
    while d < total - 1.0:
        remaining = total - d
        # Wind is evaluated toward where this throw is headed
        here = region.point_along_route(route, d)
        probe = region.point_along_route(route, min(d + min(reach_limit, remaining), total))
        headwind, _ = wind_components(wind_speed, wind_from_deg, bearing_between(*here, *probe))
        limit = effective_throw_distance(reach_limit, headwind)
        if mode == "balanced":
            limit *= 0.95
        limit = max(limit, MIN_THROW_FT)

        target_d = min(d + limit, total)
        for corner_d in corners:
            if d + MIN_THROW_FT < corner_d < target_d - 1.0:
                target_d = corner_d
                break
        spans.append((d, target_d))
        d = target_d
    return spans


def recommend_route(
    region: FairwayRegion,
    route: list,  # derived playing line from the start (tee or lie) to the basket
    discs: list,
    disc_distances: dict,  # {disc_id: avg_distance} — best across styles
    disc_max_distances: Optional[dict] = None,
    wind_speed: float = 0.0,
    wind_direction=None,  # compass string or degrees, wind FROM
    mode: str = "balanced",
    style_distances: Optional[dict] = None,  # {style: {disc_id: avg}}
    style_max_distances: Optional[dict] = None,  # {style: {disc_id: max}}
    hand: str = "right",
    style_priority: Optional[dict] = None,  # {style: 1-based priority}
    hazard_polygons: Optional[list] = None,  # [(hazard_type, ring)]
    allowed_styles: Optional[list] = None,
    style_hands: Optional[dict] = None,
    start_is_lie: bool = False,  # live round: flags a recovery when outside
) -> list[SegmentRecommendation]:
    if len(route) < 2 or not discs:
        return []

    disc_max_distances = disc_max_distances or {}
    hazard_polygons = hazard_polygons or []
    style_hands = style_hands or {}
    if not style_distances:
        style_distances = {"backhand": disc_distances}
    if not style_max_distances:
        style_max_distances = {"backhand": disc_max_distances}
    style_priority = style_priority or {"backhand": 1, "forehand": 2}
    styles = [
        s for s, d in style_distances.items()
        if any(v for v in d.values()) and (not allowed_styles or s in allowed_styles)
    ]
    if not styles:
        styles = ["backhand"]
        style_distances = {"backhand": disc_distances}

    wind_from_deg = wind_direction_to_degrees(wind_direction)
    reach_limit = player_reach(discs, disc_distances, disc_max_distances, mode)
    if reach_limit <= 0:
        return []

    spans = plan_route_targets(region, route, reach_limit, mode, wind_speed, wind_from_deg)
    recommendations = []

    for idx, (d0, d1) in enumerate(spans):
        start_pt = region.point_along_route(route, d0)
        target_pt = region.point_along_route(route, d1)
        distance = d1 - d0  # along the corridor: what the flight must cover
        is_final = idx == len(spans) - 1

        throw_bearing = bearing_between(*start_pt, *target_pt)
        headwind, crosswind = wind_components(wind_speed, wind_from_deg, throw_bearing)

        # Finish angle: where the NEXT throw goes relative to this one
        finish_deg = 0.0
        if not is_final:
            next_pt = region.point_along_route(route, spans[idx + 1][1])
            finish_deg = angle_diff(bearing_between(*target_pt, *next_pt), throw_bearing)
        finish_deg_adjusted = finish_deg + CROSSWIND_DRIFT_DEG_PER_MPH * crosswind

        throw_type = classify_throw(distance, is_final=is_final, reach=reach_limit)
        # Tightness reads the corridor the flight actually crosses — pad off
        # the span ends so the fairway's end caps (right behind the tee, right
        # past the basket) don't make every hole read as a tunnel.
        pad = min(40.0, (d1 - d0) * 0.25)
        tightness = clearance_to_tightness(region.min_clearance_along(route, d0 + pad, d1 - pad))
        is_recovery = idx == 0 and start_is_lie and not region.contains(*route[0])

        # Evaluate every (style, disc) pair — unchanged scoring core
        best = None  # (score, disc, style, normalized, effort)
        for style in styles:
            distances = style_distances.get(style, {})
            if not any(distances.values()):
                continue
            max_dists = style_max_distances.get(style, {}) or {}

            throw_hand = style_hands.get(style, hand)
            normalized = finish_deg_adjusted if style_finishes_left(throw_hand, style) else -finish_deg_adjusted
            desired_stability = max(-3.0, min(4.0, -normalized / 15.0))

            def carry(d, _distances=distances):
                base = _distances.get(d.disc_id, 0) or 0
                return effective_throw_distance(base, headwind)

            def max_carry(d, _max=max_dists, _distances=distances):
                base = _max.get(d.disc_id) or _distances.get(d.disc_id, 0) or 0
                return effective_throw_distance(base, headwind)

            def effort_for(d, _distances=distances, _max=max_dists):
                avg = effective_throw_distance(_distances.get(d.disc_id, 0) or 0, headwind)
                dmax = effective_throw_distance(_max.get(d.disc_id, 0) or 0, headwind)
                return throw_effort(distance, avg, dmax)

            with_data = [d for d in discs if distances.get(d.disc_id)]
            if not with_data:
                continue
            capable = [d for d in with_data if max_carry(d) >= distance - REACH_TOLERANCE_FT]
            if not capable:
                capable = [max(with_data, key=max_carry)]

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

        shot_shape = derive_shot_shape(best_normalized, best_disc, best_effort, distance)
        landing_zone = landing_zone_for(distance, throw_type, is_final, mode)
        rationale = build_rationale(best_disc, shot_shape, tightness, distance, best_effort)
        if is_recovery:
            rationale = "Recovery — get back in the fairway. " + rationale

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
            start_latitude=start_pt[0],
            start_longitude=start_pt[1],
            target_latitude=target_pt[0],
            target_longitude=target_pt[1],
            is_recovery=is_recovery,
            # The flight follows the derived route's corridor, not the straight
            # chord — tag hazards the route span actually crosses, so a shaped
            # line that bends around drawn trees isn't falsely warned.
            hazards=[
                htype for htype, poly in hazard_polygons
                if _span_crosses_polygon(region, route, d0, d1, poly)
            ],
        ))

    return recommendations


def _span_crosses_polygon(region, route, d0: float, d1: float, poly, step_ft: float = 25.0) -> bool:
    """Does the route between distances d0..d1 enter the polygon? Sampled at
    step_ft so a throw is judged on the corridor it actually flies."""
    pts = []
    d = d0
    while True:
        pts.append(region.point_along_route(route, min(d, d1)))
        if d >= d1:
            break
        d += step_ft
    return any(
        segment_crosses_polygon(a[0], a[1], b[0], b[1], poly)
        for a, b in zip(pts, pts[1:])
    )
