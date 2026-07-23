import math
import pytest

from app.utils import haversine_feet, bearing_between, angle_diff
from app.fairway import FairwayRegion
from app.recommendation import (
    wind_direction_to_degrees,
    wind_components,
    effective_throw_distance,
    derive_shot_shape,
    disc_net_stability,
    recommend_route,
)

LAT0, LNG0 = 40.0, -90.0
LNG_FT = 364000.0 * math.cos(math.radians(LAT0))


def ll(x_ft, y_ft):
    return (LAT0 + y_ft / 364000.0, LNG0 + x_ft / LNG_FT)


def corridor(length_ft: float, width_ft: float = 60.0):
    """Straight north corridor with tee at the south end, basket at the north.
    Returns (region, route) — route derived at the balanced margin."""
    half = width_ft / 2
    ring = [ll(-half, -10), ll(half, -10), ll(half, length_ft + 10), ll(-half, length_ft + 10)]
    region = FairwayRegion(ring)
    route = region.route(ll(0, 0), ll(0, length_ft), erosion_ft=15)
    return region, route


class FakeDisc:
    def __init__(self, disc_id, name, fade=0.0, turn=0.0, speed=9.0, manufacturer="Test"):
        self.disc_id = disc_id
        self.name = name
        self.manufacturer = manufacturer
        self.fade = fade
        self.turn = turn
        self.speed = speed


# --- geometry utils ---

def test_bearing_north_and_east():
    assert bearing_between(0.0, 0.0, 1.0, 0.0) == pytest.approx(0.0, abs=0.01)
    assert bearing_between(0.0, 0.0, 0.0, 1.0) == pytest.approx(90.0, abs=0.01)


def test_angle_diff_wraps():
    assert angle_diff(350.0, 10.0) == pytest.approx(-20.0)
    assert angle_diff(10.0, 350.0) == pytest.approx(20.0)
    assert angle_diff(180.0, 0.0) == pytest.approx(180.0)


def test_haversine_feet_one_degree_lat():
    assert haversine_feet(0.0, 0.0, 1.0, 0.0) == pytest.approx(364000, rel=0.01)


# --- wind ---

def test_wind_direction_parsing():
    assert wind_direction_to_degrees("N") == 0.0
    assert wind_direction_to_degrees("SW") == 225.0
    assert wind_direction_to_degrees(123.0) == 123.0
    assert wind_direction_to_degrees(None) is None


def test_wind_components_headwind():
    head, cross = wind_components(10.0, 0.0, 0.0)
    assert head == pytest.approx(10.0)
    assert cross == pytest.approx(0.0)


def test_wind_components_tailwind_and_crosswind():
    head, cross = wind_components(10.0, 180.0, 0.0)
    assert head == pytest.approx(-10.0)
    head, cross = wind_components(10.0, 90.0, 0.0)
    assert head == pytest.approx(0.0, abs=0.01)
    assert cross == pytest.approx(10.0)


def test_effective_throw_distance():
    assert effective_throw_distance(300.0, 10.0) == pytest.approx(270.0)   # headwind
    assert effective_throw_distance(300.0, -10.0) == pytest.approx(315.0)  # tailwind


# --- shot shapes ---

def test_derive_shot_shape():
    assert derive_shot_shape(0.0) == "straight"
    assert derive_shot_shape(-20.0) == "hyzer"
    assert derive_shot_shape(20.0) == "anhyzer"
    assert derive_shot_shape(-55.0) == "spike_hyzer"


def test_derive_shot_shape_depends_on_disc():
    overstable = FakeDisc(1, "Firebird", fade=3.0, turn=0.0)   # net +3
    understable = FakeDisc(2, "Sidewinder", fade=1.0, turn=-3.0)  # net -2
    assert derive_shot_shape(55.0, overstable) == "flex"
    assert derive_shot_shape(55.0, understable) == "turnover"
    assert derive_shot_shape(0.0, understable, effort=0.5) == "hyzer_flip"
    assert derive_shot_shape(0.0, understable, effort=0.0) == "straight"


def test_spike_hyzer_only_on_short_throws():
    disc = FakeDisc(1, "Firebird", fade=4.0, turn=0.0)
    assert derive_shot_shape(-55.0, disc, distance=100) == "spike_hyzer"
    assert derive_shot_shape(-55.0, disc, distance=300) == "hyzer"


def test_disc_net_stability():
    assert disc_net_stability(FakeDisc(1, "Firebird", fade=3.5, turn=0.0)) == 3.5
    assert disc_net_stability(FakeDisc(2, "Sidewinder", fade=1.0, turn=-3.0)) == -2.0


def test_throw_effort_controlled_vs_max():
    from app.recommendation import throw_effort
    assert throw_effort(250, 300, 350) == 0.0
    assert throw_effort(325, 300, 350) == pytest.approx(0.5)
    assert throw_effort(350, 300, 350) == pytest.approx(1.0)
    assert throw_effort(400, 300, 350) > 1.0


# --- route walking (replaces the node-chain lookahead) ---

def test_one_throw_when_basket_in_reach():
    region, route = corridor(300)
    recs = recommend_route(
        region=region, route=route,
        discs=[FakeDisc(1, "Wraith", fade=3.0, turn=-1.0)],
        disc_distances={1: 350}, mode="balanced",
    )
    assert len(recs) == 1
    assert recs[0].target_latitude is not None


def test_two_throws_when_out_of_reach():
    region, route = corridor(300)
    recs = recommend_route(
        region=region, route=route,
        discs=[FakeDisc(1, "Wraith", fade=3.0, turn=-1.0)],
        disc_distances={1: 250}, disc_max_distances={1: 260}, mode="balanced",
    )
    assert len(recs) == 2


def test_headwind_shortens_the_plan():
    region, route = corridor(300)
    discs = [FakeDisc(1, "Wraith", fade=2.0, turn=-1.0)]
    calm = recommend_route(
        region=region, route=route, discs=discs,
        disc_distances={1: 320}, disc_max_distances={1: 330}, mode="balanced",
    )
    assert len(calm) == 1

    windy = recommend_route(
        region=region, route=route, discs=discs,
        disc_distances={1: 320}, disc_max_distances={1: 330},
        wind_speed=20.0, wind_direction="N", mode="balanced",
    )
    assert len(windy) == 2
    assert windy[0].effective_distance > windy[0].distance  # plays longer into wind


def test_aggressive_uses_max_distance():
    region, route = corridor(300)
    discs = [FakeDisc(1, "Wraith", fade=2.0, turn=-1.0)]
    balanced = recommend_route(
        region=region, route=route, discs=discs,
        disc_distances={1: 250}, disc_max_distances={1: 320}, mode="balanced",
    )
    assert len(balanced) == 2

    aggressive = recommend_route(
        region=region, route=route, discs=discs,
        disc_distances={1: 250}, disc_max_distances={1: 320}, mode="aggressive",
    )
    assert len(aggressive) == 1


def test_empty_inputs():
    region, route = corridor(300)
    assert recommend_route(region=region, route=[], discs=[], disc_distances={}) == []
    assert recommend_route(region=region, route=route, discs=[], disc_distances={}) == []


# --- fairway-aware disc selection (tightness now measured from the polygon) ---

def dd3():
    return FakeDisc(1, "DD3", fade=2.0, turn=-1.0, speed=12.0)  # lateral 3


def dimension():
    return FakeDisc(2, "Dimension", fade=2.0, turn=-3.0, speed=14.0)  # lateral 5


def test_tunnel_prefers_low_lateral_disc():
    """24ft-wide tunnel: clearance ~12ft reads as tightness 1.0 — the
    controllable DD3 beats the wide Dimension without any width tagging."""
    region, route = corridor(430, width_ft=24)
    recs = recommend_route(
        region=region, route=route,
        discs=[dd3(), dimension()],
        disc_distances={1: 430, 2: 430},
        disc_max_distances={1: 460, 2: 470},
        mode="balanced",
    )
    assert recs[0].disc == "Test DD3"
    assert "tunnel" in recs[0].rationale


def test_open_fairway_allows_wide_disc():
    """Full send on an open hole: only the Dimension's max line reaches, and
    the open fairway (clearance ~60ft -> tightness 0) makes its lateral
    movement free — the wide disc wins."""
    region, route = corridor(450, width_ft=120)
    recs = recommend_route(
        region=region, route=route,
        discs=[dd3(), dimension()],
        disc_distances={1: 425, 2: 450},
        disc_max_distances={1: 430, 2: 470},
        mode="aggressive",
    )
    assert len(recs) == 1
    assert recs[0].disc == "Test Dimension"
    assert "open" in recs[0].rationale


def test_hyzer_flip_for_understable_reach():
    """Reaching past the controlled average (aggressive single throw) on a
    straight line with an understable disc is the flip-and-ride play."""
    region, route = corridor(380, width_ft=60)
    understable = FakeDisc(1, "Leopard", fade=1.0, turn=-3.0, speed=7.0)
    recs = recommend_route(
        region=region, route=route,
        discs=[understable],
        disc_distances={1: 370}, disc_max_distances={1: 410},
        mode="aggressive",
    )
    assert len(recs) == 1
    assert recs[0].shot_shape == "hyzer_flip"


# --- risk-mode landing zones ---

def test_landing_zone_by_mode():
    from app.recommendation import landing_zone_for
    assert landing_zone_for(30, "putt", True, "balanced") == "c1"
    assert landing_zone_for(50, "putt", True, "balanced") == "c2"
    assert landing_zone_for(120, "approach", True, "aggressive") == "c1"
    assert landing_zone_for(120, "approach", True, "conservative") == "c2"
    assert landing_zone_for(200, "drive", False, "aggressive") == "fairway"


def test_recommendation_carries_flight_numbers_and_zone():
    region, route = corridor(45)
    putter = FakeDisc(1, "Judge", fade=0.0, turn=0.0, speed=2.0)
    recs = recommend_route(
        region=region, route=route,
        discs=[putter], disc_distances={1: 220}, mode="balanced",
    )
    assert recs[0].speed == 2.0
    assert recs[0].turn == 0.0
    assert recs[0].fade == 0.0
    assert recs[0].throw_type == "putt"
    assert recs[0].landing_zone in ("c1", "c2")


# --- polygon-native behaviors ---

def test_recovery_flagged_when_lie_outside_fairway():
    region, _ = corridor(300)
    lie = ll(90, 150)  # 60ft right of the fairway edge
    route = region.route(lie, ll(0, 300), erosion_ft=15)
    recs = recommend_route(
        region=region, route=route,
        discs=[FakeDisc(1, "Wraith", fade=2.0, turn=-1.0)],
        disc_distances={1: 250}, mode="balanced",
        start_is_lie=True,
    )
    assert recs[0].is_recovery
    assert "Recovery" in recs[0].rationale
    # subsequent throws are normal
    assert all(not r.is_recovery for r in recs[1:])


def test_hazard_route_tagging():
    region, route = corridor(300)
    strip = [ll(-40, 140), ll(40, 140), ll(40, 160), ll(-40, 160)]  # across the fairway
    recs = recommend_route(
        region=region, route=route,
        discs=[FakeDisc(1, "Wraith", fade=2.0, turn=-1.0)],
        disc_distances={1: 350}, mode="aggressive",
        hazard_polygons=[("water", strip)],
    )
    assert len(recs) == 1
    assert "water" in recs[0].hazards


def test_hazard_not_tagged_when_route_bends_around():
    """A shaped line that follows the corridor around a hazard shouldn't be
    warned just because the straight chord clips it."""
    from app.fairway import corridor_ring
    import math as _m
    # 40deg dogleg: bend is shapeable (<50deg cap), so one throw flies it
    bend = _m.radians(40)
    elbow = (0.0, 200.0)
    basket_xy = (200 * _m.sin(bend), 200 + 200 * _m.cos(bend))
    ring = corridor_ring([ll(0, 0), ll(*elbow), ll(*basket_xy)], half_width_ft=30)
    region = FairwayRegion(ring)
    route = region.route(ll(0, 0), ll(*basket_xy), erosion_ft=15)
    # hazard in the elbow, outside the fairway: the tee->basket chord crosses
    # it, the routed corridor does not
    box = [ll(60, 190), ll(90, 190), ll(90, 220), ll(60, 220)]
    recs = recommend_route(
        region=region, route=route,
        discs=[FakeDisc(1, "Wraith", fade=2.0, turn=-1.0)],
        disc_distances={1: 450}, mode="balanced",
        hazard_polygons=[("trees", box)],
    )
    assert len(recs) == 1
    assert recs[0].hazards == []


def test_turn_side_shape_risk_penalty():
    """A committed anhyzer/turnover line costs SHAPE_RISK_PENALTY vs the
    mirror-image hyzer at identical flight fit."""
    from app.recommendation import score_disc, SHAPE_RISK_PENALTY
    d = FakeDisc(1, "Neutral", fade=1.0, turn=-1.0)  # net stability 0
    hyzer_side = score_disc(d, 300, 300, desired_stability=1.0)
    anny_side = score_disc(d, 300, 300, desired_stability=-1.0)
    assert hyzer_side - anny_side == pytest.approx(SHAPE_RISK_PENALTY)
