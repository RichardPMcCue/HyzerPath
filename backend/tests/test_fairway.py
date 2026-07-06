import math

import pytest

from app.fairway import FairwayRegion, clearance_to_tightness

LAT0, LNG0 = 40.0, -90.0
LNG_FT = 364000.0 * math.cos(math.radians(LAT0))


def ll(x_ft: float, y_ft: float) -> tuple:
    """Local feet → (lat, lng) around the test origin."""
    return (LAT0 + y_ft / 364000.0, LNG0 + x_ft / LNG_FT)


def rect(x0, y0, x1, y1) -> list:
    return [ll(x0, y0), ll(x1, y0), ll(x1, y1), ll(x0, y1)]


# 400ft straight corridor, 60ft wide
STRAIGHT = rect(-30, 0, 30, 400)

# L-shaped dogleg: north leg x∈[-30,30] y∈[0,400], east leg y∈[340,400] x∈[-30,400]
DOGLEG = [
    ll(-30, 0), ll(30, 0), ll(30, 340), ll(400, 340), ll(400, 400), ll(-30, 400),
]


def test_straight_route_is_straight():
    r = FairwayRegion(STRAIGHT)
    route = r.route(ll(0, 5), ll(0, 395), erosion_ft=15)
    assert r.route_length_ft(route) == pytest.approx(390, abs=5)


def test_dogleg_route_bends_and_stays_inside():
    r = FairwayRegion(DOGLEG)
    route = r.route(ll(0, 10), ll(390, 370), erosion_ft=5)
    assert len(route) >= 3  # must turn the corner, not cut it
    # every step of the polyline stays inside the fairway
    for a, b in zip(route, route[1:]):
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        assert r.contains(*mid), f"segment midpoint {mid} left the fairway"


def test_aggressive_cuts_tighter_than_conservative():
    r = FairwayRegion(DOGLEG)
    tee, basket = ll(0, 10), ll(390, 370)
    aggressive = r.route_length_ft(r.route(tee, basket, erosion_ft=5))
    conservative = r.route_length_ft(r.route(tee, basket, erosion_ft=25))
    assert aggressive < conservative


def test_erosion_steps_down_in_tunnel():
    # 20ft-wide tunnel: 25ft erosion annihilates it, route must still exist
    r = FairwayRegion(rect(-10, 0, 10, 300))
    route = r.route(ll(0, 5), ll(0, 295), erosion_ft=25)
    assert r.route_length_ft(route) == pytest.approx(290, abs=5)


def test_tee_outside_polygon_still_routes_from_tee():
    r = FairwayRegion(STRAIGHT)
    tee = ll(0, -15)  # concrete pad behind the grass line
    route = r.route(tee, ll(0, 395), erosion_ft=15)
    assert route[0] == tee
    assert r.route_length_ft(route) == pytest.approx(410, abs=6)


def test_contains_and_clearance():
    r = FairwayRegion(STRAIGHT)
    assert r.contains(*ll(0, 200))
    assert not r.contains(*ll(100, 200))
    assert r.clearance_ft(*ll(0, 200)) == pytest.approx(30, abs=1)   # center of 60ft
    assert r.clearance_ft(*ll(25, 200)) == pytest.approx(5, abs=1)   # near the edge
    assert r.clearance_ft(*ll(100, 200)) == 0.0                      # outside


def test_min_clearance_along_throw():
    r = FairwayRegion(STRAIGHT)
    # a throw drifting from center to the edge: tightest point governs
    c = r.min_clearance_ft(ll(0, 50), ll(25, 350))
    assert c == pytest.approx(5, abs=2)


def test_point_along_route_interpolates():
    r = FairwayRegion(STRAIGHT)
    route = [ll(0, 0), ll(0, 400)]
    lat, lng = r.point_along_route(route, 100)
    assert (lat, lng) == pytest.approx(ll(0, 100), abs=1e-6)
    # past the end clamps to the end
    assert r.point_along_route(route, 999) == route[-1]


def test_nearest_inside_recovery_target():
    r = FairwayRegion(STRAIGHT)
    lat, lng = r.nearest_inside(*ll(80, 200))  # 50ft right of the fairway
    assert r.contains(lat, lng)
    assert r.clearance_ft(lat, lng) >= 5  # pulled past the edge, not on it


def test_hazard_subtraction_reroutes():
    # OB square biting into the right half of the corridor mid-hole
    hazard = rect(0, 180, 40, 220)
    safe = FairwayRegion(STRAIGHT, [hazard], subtract_hazards=True)
    raw = FairwayRegion(STRAIGHT)
    tee, basket = ll(20, 5), ll(20, 395)
    safe_route = safe.route(tee, basket, erosion_ft=5)
    # the safe route must dodge left around the bite
    assert any(lng < ll(0, 0)[1] for _, lng in safe_route[1:-1])
    # while the raw region routes straight through
    assert raw.route_length_ft(raw.route(tee, basket, erosion_ft=5)) == pytest.approx(390, abs=5)


def test_clearance_to_tightness_mapping():
    assert clearance_to_tightness(40) == 0.0
    assert clearance_to_tightness(12) == 1.0
    assert 0.0 < clearance_to_tightness(24) < 1.0
