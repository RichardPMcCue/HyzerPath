def make_course(client):
    return client.post("/courses", json={
        "name": "Map Test", "city": "Test", "state": "TS",
        "address": "", "total_par": 0
    }).json()["course_id"]


def make_hole(client, cid):
    return client.post(f"/courses/{cid}/holes", json={
        "hole_number": 1, "par": 3, "distance": 0, "elevation": 0
    }).json()["hole_id"]


def add_node(client, cid, hid, node_type, seq, lat, lng):
    return client.post(f"/courses/{cid}/holes/{hid}/nodes", json={
        "node_type": node_type, "sequence": seq, "latitude": lat,
        "longitude": lng, "is_fairway": True
    }).json()["hole_node_id"]


def add_disc(client):
    """Recommendations only exist when the player has a disc with a distance."""
    disc_id = client.post("/bag/discs", json={
        "name": "Destroyer", "manufacturer": "Innova",
        "disc_type": "distance_driver", "speed": 12.0, "glide": 5.0,
        "turn": -1.0, "fade": 3.0
    }).json()["disc_id"]
    client.put(f"/bag/discs/{disc_id}/stats", json={"avg_distance": 350, "max_distance": 420})


# ~0.000275 deg lat ≈ 100 ft
def test_rebuild_edges_chain_and_dogleg_distance(client):
    cid = make_course(client)
    hid = make_hole(client, cid)
    add_node(client, cid, hid, "tee", 0, 40.0, -90.0)
    add_node(client, cid, hid, "landing_zone", 1, 40.000550, -90.0)      # 200 ft north
    add_node(client, cid, hid, "landing_zone", 2, 40.000550, -90.000718)  # then 200 ft west
    add_node(client, cid, hid, "basket", 3, 40.001100, -90.000718)       # then 200 ft north

    edges = client.post(f"/courses/{cid}/holes/{hid}/edges/rebuild").json()
    # 4 GPS nodes → consecutive (3) + skip-one (2, tee→basket excluded) = 5
    assert len(edges) == 5

    hole = next(h for h in client.get(f"/courses/{cid}").json()["holes"])
    # dogleg length ≈ 600 ft along the chain, not the ~480 ft crow-fly line
    assert 560 <= hole["distance"] <= 640


def test_rebuild_edges_no_direct_line_with_one_waypoint(client):
    cid = make_course(client)
    hid = make_hole(client, cid)
    tee = add_node(client, cid, hid, "tee", 0, 40.0, -90.0)
    add_node(client, cid, hid, "landing_zone", 1, 40.000550, -90.000718)
    basket = add_node(client, cid, hid, "basket", 2, 40.001100, 0 - 90.0)

    edges = client.post(f"/courses/{cid}/holes/{hid}/edges/rebuild").json()
    pairs = {(e["from_node_id"], e["to_node_id"]) for e in edges}
    assert (tee, basket) not in pairs  # dogleg can't be cut
    assert len(edges) == 2


def test_hazard_polygon_tags_crossing_edges(client):
    add_disc(client)
    cid = make_course(client)
    hid = make_hole(client, cid)
    add_node(client, cid, hid, "tee", 0, 40.0, -90.0)
    add_node(client, cid, hid, "basket", 1, 40.001100, -90.0)  # 400 ft north
    client.post(f"/courses/{cid}/holes/{hid}/edges/rebuild")

    # OB strip straddling the line halfway up
    hazard = client.post(f"/courses/{cid}/holes/{hid}/hazards", json={
        "hazard_type": "ob",
        "polygon": [
            [40.000400, -90.000300],
            [40.000400, -89.999700],
            [40.000700, -89.999700],
            [40.000700, -90.000300]
        ]
    })
    assert hazard.status_code == 200

    path = client.get(f"/courses/{cid}/holes/{hid}/path").json()
    assert len(path["hazards"]) == 1
    assert path["hazards"][0]["hazard_type"] == "ob"
    # the tee→basket recommendation crosses the strip → engine sees the hazard
    assert any("ob" in rec["hazards"] for rec in path["recommendations"])


def test_hazard_delete_untags_edges(client):
    add_disc(client)
    cid = make_course(client)
    hid = make_hole(client, cid)
    add_node(client, cid, hid, "tee", 0, 40.0, -90.0)
    add_node(client, cid, hid, "basket", 1, 40.001100, -90.0)
    client.post(f"/courses/{cid}/holes/{hid}/edges/rebuild")
    hz = client.post(f"/courses/{cid}/holes/{hid}/hazards", json={
        "hazard_type": "water",
        "polygon": [[40.0004, -90.0003], [40.0004, -89.9997], [40.0007, -89.9997]]
    }).json()

    client.delete(f"/courses/{cid}/holes/{hid}/hazards/{hz['hazard_id']}")
    path = client.get(f"/courses/{cid}/holes/{hid}/path").json()
    assert path["hazards"] == []
    assert all(rec["hazards"] == [] for rec in path["recommendations"])


def test_non_crossing_hazard_not_tagged(client):
    add_disc(client)
    cid = make_course(client)
    hid = make_hole(client, cid)
    add_node(client, cid, hid, "tee", 0, 40.0, -90.0)
    add_node(client, cid, hid, "basket", 1, 40.001100, -90.0)
    client.post(f"/courses/{cid}/holes/{hid}/edges/rebuild")
    # pond well off to the east of the line
    client.post(f"/courses/{cid}/holes/{hid}/hazards", json={
        "hazard_type": "water",
        "polygon": [[40.0004, -89.99], [40.0004, -89.98], [40.0007, -89.98]]
    })
    path = client.get(f"/courses/{cid}/holes/{hid}/path").json()
    assert all(rec["hazards"] == [] for rec in path["recommendations"])


def test_delete_waypoint_node(client):
    cid = make_course(client)
    hid = make_hole(client, cid)
    add_node(client, cid, hid, "tee", 0, 40.0, -90.0)
    lz = add_node(client, cid, hid, "landing_zone", 1, 40.000550, -90.000718)
    add_node(client, cid, hid, "basket", 2, 40.001100, -90.0)
    client.post(f"/courses/{cid}/holes/{hid}/edges/rebuild")

    r = client.delete(f"/courses/{cid}/holes/{hid}/nodes/{lz}")
    assert r.status_code == 200
    nodes = client.get(f"/courses/{cid}/holes/{hid}/nodes").json()
    assert len(nodes) == 2
