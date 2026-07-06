import math

LAT0, LNG0 = 40.0, -90.0
LNG_FT = 364000.0 * math.cos(math.radians(LAT0))


def ll(x_ft, y_ft):
    """Local feet → [lat, lng] around the test origin."""
    return [LAT0 + y_ft / 364000.0, LNG0 + x_ft / LNG_FT]


def make_course(client):
    return client.post("/courses", json={
        "name": "Map Test", "city": "Test", "state": "TS",
        "address": "", "total_par": 0
    }).json()["course_id"]


def make_hole(client, cid, polygon=None):
    hole = {"hole_number": 1, "par": 3, "distance": 0, "elevation": 0}
    if polygon is not None:
        hole["fairway_polygon"] = polygon
    return client.post(f"/courses/{cid}/holes", json=hole).json()["hole_id"]


def add_node(client, cid, hid, node_type, seq, pt):
    return client.post(f"/courses/{cid}/holes/{hid}/nodes", json={
        "node_type": node_type, "sequence": seq,
        "latitude": pt[0], "longitude": pt[1], "is_fairway": True
    }).json()["hole_node_id"]


def add_disc(client):
    """Recommendations only exist when the player has a disc with a distance."""
    disc_id = client.post("/bag/discs", json={
        "name": "Destroyer", "manufacturer": "Innova",
        "disc_type": "distance_driver", "speed": 12.0, "glide": 5.0,
        "turn": -1.0, "fade": 3.0
    }).json()["disc_id"]
    client.put(f"/bag/discs/{disc_id}/stats", json={"avg_distance": 350, "max_distance": 420})


# Straight 400ft hole in a 60ft corridor
def straight_hole(client, cid, polygon=True):
    ring = [ll(-30, -10), ll(30, -10), ll(30, 410), ll(-30, 410)] if polygon else None
    hid = make_hole(client, cid, ring)
    add_node(client, cid, hid, "tee", 0, ll(0, 0))
    add_node(client, cid, hid, "basket", 1, ll(0, 400))
    return hid


# 90° right dogleg: 200ft north, then 200ft east, 60ft-wide L fairway,
# with a trees area squatting on the inside of the corner.
def dogleg_with_corner_trees(client, cid):
    ring = [ll(-30, 0), ll(30, 0), ll(30, 170), ll(230, 170), ll(230, 230), ll(-30, 230)]
    hid = make_hole(client, cid, ring)
    add_node(client, cid, hid, "tee", 0, ll(0, 10))
    add_node(client, cid, hid, "basket", 1, ll(200, 200))
    client.post(f"/courses/{cid}/holes/{hid}/hazards", json={
        "hazard_type": "trees",
        "polygon": [ll(15, 155), ll(70, 155), ll(70, 185), ll(15, 185)],
    })
    return hid


def test_hole_distance_recomputed_from_polygon(client):
    cid = make_course(client)
    hid = straight_hole(client, cid)
    # setting the polygon after nodes exist recomputes the routed length
    r = client.patch(f"/courses/{cid}/holes/{hid}", json={
        "fairway_polygon": [ll(-30, -10), ll(30, -10), ll(30, 410), ll(-30, 410)]
    })
    assert r.status_code == 200
    assert 380 <= r.json()["distance"] <= 420  # straight 400ft hole


def test_path_without_polygon_synthesizes_corridor(client):
    """Holes mapped with only tee + basket still plan: a straight 60ft
    corridor is synthesized around the line."""
    add_disc(client)
    cid = make_course(client)
    hid = straight_hole(client, cid, polygon=False)
    path = client.get(f"/courses/{cid}/holes/{hid}/path").json()
    assert len(path["fairway_polygon"]) >= 4
    assert len(path["recommendations"]) >= 1
    assert path["total_distance"] > 350


def test_recommendations_carry_targets(client):
    add_disc(client)
    cid = make_course(client)
    hid = straight_hole(client, cid)
    path = client.get(f"/courses/{cid}/holes/{hid}/path").json()
    for rec in path["recommendations"]:
        assert rec["target_latitude"] is not None
        assert rec["start_latitude"] is not None


def test_dogleg_corner_caps_every_mode(client):
    """A 90° corner can't be wrapped by one flight: every mode plays it as
    corner placement + attack, never a single throw."""
    add_disc(client)
    cid = make_course(client)
    hid = dogleg_with_corner_trees(client, cid)
    for mode in ("conservative", "balanced", "aggressive"):
        recs = client.get(f"/courses/{cid}/holes/{hid}/path?mode={mode}").json()["recommendations"]
        assert len(recs) == 2, f"{mode} should place at the corner then attack"


def test_safe_avoids_corner_trees_aggressive_gets_warned(client):
    """Conservative/balanced carve the trees out of the routable fairway and
    swing wide (no warnings). Aggressive hugs the corner through them — and
    the plan says so."""
    add_disc(client)
    cid = make_course(client)
    hid = dogleg_with_corner_trees(client, cid)

    safe_total = 0.0
    for mode in ("conservative", "balanced"):
        path = client.get(f"/courses/{cid}/holes/{hid}/path?mode={mode}").json()
        assert all(r["hazards"] == [] for r in path["recommendations"]), mode
        safe_total = path["total_distance"]

    aggro = client.get(f"/courses/{cid}/holes/{hid}/path?mode=aggressive").json()
    assert any("trees" in r["hazards"] for r in aggro["recommendations"])
    # the corner-hugging line is shorter than the safe line around the trees
    assert aggro["total_distance"] < safe_total


def test_hazard_crud_roundtrip(client):
    add_disc(client)
    cid = make_course(client)
    hid = straight_hole(client, cid)
    hz = client.post(f"/courses/{cid}/holes/{hid}/hazards", json={
        "hazard_type": "water",
        "polygon": [ll(-40, 180), ll(40, 180), ll(40, 220), ll(-40, 220)],
    }).json()

    path = client.get(f"/courses/{cid}/holes/{hid}/path?mode=aggressive").json()
    assert len(path["hazards"]) == 1
    assert any("water" in r["hazards"] for r in path["recommendations"])

    client.delete(f"/courses/{cid}/holes/{hid}/hazards/{hz['hazard_id']}")
    path = client.get(f"/courses/{cid}/holes/{hid}/path?mode=aggressive").json()
    assert path["hazards"] == []
    assert all(r["hazards"] == [] for r in path["recommendations"])


def test_non_crossing_hazard_not_tagged(client):
    add_disc(client)
    cid = make_course(client)
    hid = straight_hole(client, cid)
    # pond well off to the east of the corridor
    client.post(f"/courses/{cid}/holes/{hid}/hazards", json={
        "hazard_type": "water",
        "polygon": [ll(300, 180), ll(400, 180), ll(400, 220), ll(300, 220)],
    })
    path = client.get(f"/courses/{cid}/holes/{hid}/path").json()
    assert all(r["hazards"] == [] for r in path["recommendations"])


def test_recovery_from_lie_outside_fairway(client):
    add_disc(client)
    cid = make_course(client)
    hid = straight_hole(client, cid)
    off = ll(100, 200)  # 70ft right of the corridor
    path = client.get(
        f"/courses/{cid}/holes/{hid}/path?lie_latitude={off[0]}&lie_longitude={off[1]}"
    ).json()
    recs = path["recommendations"]
    assert recs[0]["is_recovery"] is True
    assert all(r["is_recovery"] is False for r in recs[1:])


def test_delete_node(client):
    cid = make_course(client)
    hid = straight_hole(client, cid)
    nodes = client.get(f"/courses/{cid}/holes/{hid}/nodes").json()
    tee = next(n for n in nodes if n["node_type"] == "tee")
    r = client.delete(f"/courses/{cid}/holes/{hid}/nodes/{tee['hole_node_id']}")
    assert r.status_code == 200
    assert len(client.get(f"/courses/{cid}/holes/{hid}/nodes").json()) == 1
