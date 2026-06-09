import math
import pytest

from app.utils import haversine_feet, bearing_between, angle_diff
from app.recommendation import (
    wind_direction_to_degrees,
    wind_components,
    effective_throw_distance,
    derive_shot_shape,
    disc_net_stability,
    plan_segments,
    recommend_path,
)

LAT_DEG_PER_FOOT = 1.0 / 364000.0


class FakeHazard:
    def __init__(self, hazard_type):
        self.hazard_type = hazard_type


class FakeNode:
    def __init__(self, node_id, lat=None, lon=None, node_type="landing_zone",
                 sequence=0, is_fairway=True, centerline_distance=None):
        self.hole_node_id = node_id
        self.latitude = lat
        self.longitude = lon
        self.node_type = node_type
        self.sequence = sequence
        self.is_fairway = is_fairway
        self.centerline_distance = centerline_distance


class FakeEdge:
    def __init__(self, from_id, to_id, distance, hazards=()):
        self.from_node_id = from_id
        self.to_node_id = to_id
        self.distance = distance
        self.fairway_width = None
        self.edge_hazards = [FakeHazard(h) for h in hazards]


class FakeDisc:
    def __init__(self, disc_id, name, fade=0.0, turn=0.0, speed=9.0, manufacturer="Test"):
        self.disc_id = disc_id
        self.name = name
        self.manufacturer = manufacturer
        self.fade = fade
        self.turn = turn
        self.speed = speed


def edge_lookup_for(edges):
    return {(e.from_node_id, e.to_node_id): e for e in edges}


# --- geometry utils ---

def test_bearing_north_and_east():
    assert bearing_between(0.0, 0.0, 1.0, 0.0) == pytest.approx(0.0, abs=0.01)
    assert bearing_between(0.0, 0.0, 0.0, 1.0) == pytest.approx(90.0, abs=0.01)


def test_angle_diff_wraps():
    assert angle_diff(350.0, 10.0) == pytest.approx(-20.0)
    assert angle_diff(10.0, 350.0) == pytest.approx(20.0)
    assert angle_diff(180.0, 0.0) == pytest.approx(180.0)


def test_haversine_feet_one_degree_lat():
    # One degree of latitude is about 364,000 feet
    assert haversine_feet(0.0, 0.0, 1.0, 0.0) == pytest.approx(364000, rel=0.01)


# --- wind ---

def test_wind_direction_parsing():
    assert wind_direction_to_degrees("N") == 0.0
    assert wind_direction_to_degrees("SW") == 225.0
    assert wind_direction_to_degrees(123.0) == 123.0
    assert wind_direction_to_degrees(None) is None


def test_wind_components_headwind():
    # Throwing north into wind from the north = pure headwind
    head, cross = wind_components(10.0, 0.0, 0.0)
    assert head == pytest.approx(10.0)
    assert cross == pytest.approx(0.0)


def test_wind_components_tailwind_and_crosswind():
    # Throwing north with wind from the south = pure tailwind
    head, cross = wind_components(10.0, 180.0, 0.0)
    assert head == pytest.approx(-10.0)
    # Wind from the east while throwing north = crosswind from the right
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
    assert derive_shot_shape(55.0) == "flex"


def test_disc_net_stability():
    assert disc_net_stability(FakeDisc(1, "Firebird", fade=3.5, turn=0.0)) == 3.5
    assert disc_net_stability(FakeDisc(2, "Sidewinder", fade=1.0, turn=-3.0)) == -2.0


# --- lookahead / pruning ---

def straight_north_path(spacing_ft, count):
    """Nodes in a straight line going north, spacing_ft apart."""
    nodes = []
    for i in range(count):
        node_type = "tee" if i == 0 else ("basket" if i == count - 1 else "landing_zone")
        nodes.append(FakeNode(i + 1, lat=i * spacing_ft * LAT_DEG_PER_FOOT, lon=0.0,
                              node_type=node_type, sequence=i))
    edges = [FakeEdge(nodes[i].hole_node_id, nodes[i + 1].hole_node_id, spacing_ft)
             for i in range(count - 1)]
    return nodes, edges


def test_lookahead_skips_to_basket_when_reachable():
    nodes, edges = straight_north_path(150, 3)  # tee -> mid -> basket, ~300ft total
    segments = plan_segments(nodes, edge_lookup_for(edges), reach_limit=350.0, mode="balanced")
    assert segments == [(0, 2)]


def test_lookahead_no_skip_when_out_of_reach():
    nodes, edges = straight_north_path(150, 3)
    segments = plan_segments(nodes, edge_lookup_for(edges), reach_limit=250.0, mode="balanced")
    assert segments == [(0, 1), (1, 2)]


def test_conservative_never_skips_past_hazards():
    nodes, edges = straight_north_path(150, 3)
    edges[1].edge_hazards = [FakeHazard("water")]
    segments = plan_segments(nodes, edge_lookup_for(edges), reach_limit=350.0, mode="conservative")
    assert segments == [(0, 1), (1, 2)]


def test_aggressive_skips_past_hazards():
    nodes, edges = straight_north_path(150, 3)
    edges[1].edge_hazards = [FakeHazard("water")]
    segments = plan_segments(nodes, edge_lookup_for(edges), reach_limit=350.0, mode="aggressive")
    assert segments == [(0, 2)]


# --- full recommendation ---

def test_recommend_path_skip_reports_skipped_nodes_and_hazards():
    nodes, edges = straight_north_path(150, 3)
    edges[1].edge_hazards = [FakeHazard("ob")]
    discs = [FakeDisc(1, "Wraith", fade=3.0, turn=-1.0)]
    recs = recommend_path(
        path_nodes=nodes,
        edge_lookup=edge_lookup_for(edges),
        discs=discs,
        disc_distances={1: 350},
        mode="balanced",
    )
    assert len(recs) == 1
    assert recs[0].from_node_id == 1
    assert recs[0].to_node_id == 3
    assert recs[0].skipped_node_ids == [2]
    assert "ob" in recs[0].hazards


def test_dogleg_left_recommends_hyzer_with_fade_disc():
    # Tee -> corner (due north), corner -> basket bends ~31 degrees left
    tee = FakeNode(1, lat=0.0, lon=0.0, node_type="tee", sequence=0)
    corner = FakeNode(2, lat=0.0006, lon=0.0, sequence=1)
    basket = FakeNode(3, lat=0.0011, lon=-0.0003, node_type="basket", sequence=2)
    nodes = [tee, corner, basket]
    edges = [FakeEdge(1, 2, 218), FakeEdge(2, 3, 212)]

    fade_disc = FakeDisc(1, "Firebird", fade=3.0, turn=0.0)
    understable_disc = FakeDisc(2, "Sidewinder", fade=1.0, turn=-3.0)
    recs = recommend_path(
        path_nodes=nodes,
        edge_lookup=edge_lookup_for(edges),
        discs=[understable_disc, fade_disc],  # understable first to prove scoring wins
        disc_distances={1: 250, 2: 250},
        mode="balanced",
    )
    assert len(recs) == 2
    assert recs[0].shot_shape == "hyzer"
    assert recs[0].disc == "Test Firebird"


def test_headwind_blocks_skip():
    # Skip is reachable in calm air but not into a 20mph headwind
    nodes, edges = straight_north_path(150, 3)
    discs = [FakeDisc(1, "Wraith", fade=2.0, turn=-1.0)]
    calm = recommend_path(
        path_nodes=nodes, edge_lookup=edge_lookup_for(edges),
        discs=discs, disc_distances={1: 320}, mode="balanced",
    )
    assert len(calm) == 1  # 300ft straight line, 320 avg: skip

    windy = recommend_path(
        path_nodes=nodes, edge_lookup=edge_lookup_for(edges),
        discs=discs, disc_distances={1: 320},
        wind_speed=20.0, wind_direction="N", mode="balanced",
    )
    assert len(windy) == 2  # 20mph headwind: carry drops to ~260, no skip
    # Plays-like distance goes up into the wind
    assert windy[0].effective_distance > windy[0].distance


def test_aggressive_uses_max_distance():
    nodes, edges = straight_north_path(150, 3)
    discs = [FakeDisc(1, "Wraith", fade=2.0, turn=-1.0)]
    balanced = recommend_path(
        path_nodes=nodes, edge_lookup=edge_lookup_for(edges),
        discs=discs, disc_distances={1: 250}, disc_max_distances={1: 320},
        mode="balanced",
    )
    assert len(balanced) == 2  # avg 250 can't reach ~300

    aggressive = recommend_path(
        path_nodes=nodes, edge_lookup=edge_lookup_for(edges),
        discs=discs, disc_distances={1: 250}, disc_max_distances={1: 320},
        mode="aggressive",
    )
    assert len(aggressive) == 1  # max 320 can


def test_empty_inputs():
    assert recommend_path(path_nodes=[], edge_lookup={}, discs=[], disc_distances={}) == []


# --- mode-aware routing (edge weights) ---

def test_edge_weight_mode_changes_route_choice():
    """A direct line over water should only win for aggressive players who
    can actually throw it. This routes Dijkstra, not just pruning."""
    from app.graph import compute_edge_weight, dijkstra

    safe1 = FakeEdge(1, 2, 230)
    safe2 = FakeEdge(2, 3, 205)
    direct = FakeEdge(1, 3, 405, hazards=("water",))

    def route(mode, reach):
        edge_tuples = [
            (e.from_node_id, e.to_node_id, compute_edge_weight(e, mode=mode, reach=reach))
            for e in (safe1, safe2, direct)
        ]
        return dijkstra(edge_tuples, 1, 3)

    assert route("conservative", reach=342) == [1, 2, 3]  # around the water
    assert route("balanced", reach=380) == [1, 2, 3]      # hazard not worth it
    assert route("aggressive", reach=430) == [1, 3]       # send it


def test_edge_weight_beyond_reach_costs_more():
    from app.graph import compute_edge_weight

    edge = FakeEdge(1, 2, 400)
    within = compute_edge_weight(edge, reach=450)
    beyond = compute_edge_weight(edge, reach=300)
    assert within == pytest.approx(1.0)
    assert beyond == pytest.approx(400 / 300)


# --- throw roles (drive / placement / approach / putt) ---

def test_classify_throw():
    from app.recommendation import classify_throw
    assert classify_throw(30, is_final=True, reach=350) == "putt"
    assert classify_throw(120, is_final=True, reach=350) == "approach"
    assert classify_throw(320, is_final=False, reach=350) == "drive"
    assert classify_throw(180, is_final=False, reach=350) == "placement"


def test_approach_prefers_controllable_disc():
    """Same distance fit, same flight: the putter beats the driver when the
    job is landing close, not covering ground."""
    nodes, edges = straight_north_path(200, 3)  # 200ft drive + 200ft approach
    driver = FakeDisc(1, "Beat Driver", fade=1.0, turn=-1.0)
    putter = FakeDisc(2, "Judge", fade=1.0, turn=-1.0)
    driver.speed = 12.0
    putter.speed = 2.0

    recs = recommend_path(
        path_nodes=nodes, edge_lookup=edge_lookup_for(edges),
        discs=[driver, putter],
        disc_distances={1: 210, 2: 210},  # identical distance profiles
        mode="conservative",  # reach 189: no skip, two throws
    )
    assert len(recs) == 2
    assert recs[-1].throw_type == "approach"
    assert recs[-1].disc == "Test Judge"


def test_final_putt_labeled():
    nodes, edges = straight_north_path(35, 2)  # one 35ft throw to the basket
    putter = FakeDisc(1, "Judge", fade=0.0, turn=0.0)
    putter.speed = 2.0
    recs = recommend_path(
        path_nodes=nodes, edge_lookup=edge_lookup_for(edges),
        discs=[putter], disc_distances={1: 220}, mode="balanced",
    )
    assert recs[0].throw_type == "putt"


# --- fairway polygon ---

def test_fairway_polygon_buffers_centerline():
    from app.utils import compute_fairway_polygon, haversine_feet

    nodes, edges = straight_north_path(200, 3)
    edges[0].fairway_width = 40
    edges[1].fairway_width = 40
    ring = compute_fairway_polygon(nodes, edges)

    # Closed ring: 3 left + 3 right + closing point
    assert len(ring) == 7
    assert ring[0] == ring[-1]
    # Corridor width at the tee: distance between first left and last right point ≈ 40ft
    left_first = ring[0]
    right_first = ring[-2]
    width = haversine_feet(left_first[0], left_first[1], right_first[0], right_first[1])
    assert width == pytest.approx(40, rel=0.05)


def test_fairway_polygon_needs_two_points():
    from app.utils import compute_fairway_polygon
    assert compute_fairway_polygon([FakeNode(1, lat=1.0, lon=1.0)], []) == []
