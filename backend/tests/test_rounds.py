def seed_course(client):
    course = client.post("/courses", json={
        "name": "Test DGC", "city": "Worcester", "state": "MA",
        "address": "1 Fairway Ln", "total_par": 6
    }).json()
    cid = course["course_id"]
    holes = []
    for n in (1, 2):
        holes.append(client.post(f"/courses/{cid}/holes", json={
            "hole_number": n, "par": 3, "distance": 300, "elevation": 0
        }).json()["hole_id"])
    return cid, holes


def seed_mapped_hole(client, cid):
    """Hole with tee -> LZ -> basket along a north line, with GPS."""
    hid = client.post(f"/courses/{cid}/holes", json={
        "hole_number": 3, "par": 3, "distance": 300, "elevation": 0
    }).json()["hole_id"]
    ids = {}
    for node_type, seq, lat in (("tee", 0, 40.0), ("landing_zone", 1, 40.0 + 150 / 364000), ("basket", 2, 40.0 + 300 / 364000)):
        ids[node_type] = client.post(f"/courses/{cid}/holes/{hid}/nodes", json={
            "node_type": node_type, "sequence": seq, "latitude": lat, "longitude": -105.0
        }).json()["hole_node_id"]
    client.post(f"/courses/{cid}/holes/{hid}/edges", json={
        "from_node_id": ids["tee"], "to_node_id": ids["landing_zone"], "distance": 150
    })
    client.post(f"/courses/{cid}/holes/{hid}/edges", json={
        "from_node_id": ids["landing_zone"], "to_node_id": ids["basket"], "distance": 150
    })
    return hid, ids


def add_disc_with_stats(client, avg=250):
    disc_id = client.post("/bag/discs", json={
        "name": "Buzzz", "manufacturer": "Discraft", "disc_type": "midrange",
        "speed": 5, "glide": 4, "turn": -1, "fade": 1
    }).json()["disc_id"]
    client.put(f"/bag/discs/{disc_id}/stats", json={"avg_distance": avg})
    return disc_id


def test_round_lifecycle(client):
    cid, holes = seed_course(client)

    round_ = client.post("/rounds", json={"course_id": cid}).json()
    rid = round_["round_id"]
    assert round_["total_score"] is None

    # score both holes; re-scoring upserts
    assert client.put(f"/rounds/{rid}/holes/{holes[0]}", json={"score": 4}).status_code == 200
    client.put(f"/rounds/{rid}/holes/{holes[1]}", json={"score": 3})
    client.put(f"/rounds/{rid}/holes/{holes[0]}", json={"score": 5})

    finished = client.post(f"/rounds/{rid}/finish").json()
    assert finished["total_score"] == 8

    fetched = client.get(f"/rounds/{rid}").json()
    assert {rh["hole_id"]: rh["score"] for rh in fetched["round_holes"]} == {holes[0]: 5, holes[1]: 3}


def test_round_starts_with_autocreated_bag(client):
    cid, _ = seed_course(client)
    round_ = client.post("/rounds", json={"course_id": cid}).json()
    assert round_["bag_id"] is not None


def test_score_unknown_hole_404(client):
    cid, _ = seed_course(client)
    rid = client.post("/rounds", json={"course_id": cid}).json()["round_id"]
    assert client.put(f"/rounds/{rid}/holes/9999", json={"score": 3}).status_code == 404


def test_path_from_lie_replans(client):
    """Marking a lie partway down the fairway replans from there: one throw
    to the basket instead of the full tee plan."""
    cid, _ = seed_course(client)
    hid, ids = seed_mapped_hole(client, cid)
    add_disc_with_stats(client, avg=250)

    # From the tee: 300ft with a 250 avg -> 2 throws
    from_tee = client.get(f"/courses/{cid}/holes/{hid}/path").json()
    assert len(from_tee["recommendations"]) == 2

    # Lie 180ft up the fairway: 120ft left -> single approach to the basket
    lie_lat = 40.0 + 180 / 364000
    from_lie = client.get(
        f"/courses/{cid}/holes/{hid}/path",
        params={"lie_latitude": lie_lat, "lie_longitude": -105.0}
    ).json()
    recs = from_lie["recommendations"]
    assert len(recs) == 1
    assert recs[0]["from_node_id"] == 0  # the virtual lie node
    assert recs[0]["to_node_id"] == ids["basket"]
    assert abs(recs[0]["distance"] - 120) <= 5
    assert recs[0]["throw_type"] == "approach"
    # The lie appears in the returned path nodes
    assert from_lie["nodes"][0]["label"] == "Your lie"


def test_record_round_throws_and_stats(client):
    """Drive into the fairway, approach to C1, holed putt -> stats add up."""
    cid, _ = seed_course(client)
    hid, ids = seed_mapped_hole(client, cid)
    disc_id = add_disc_with_stats(client, avg=250)
    rid = client.post("/rounds", json={"course_id": cid}).json()["round_id"]

    tee_lat, basket_lat = 40.0, 40.0 + 300 / 364000
    drive_end = 40.0 + 200 / 364000           # 200ft up the middle (in the corridor)
    putt_start = basket_lat - 20 / 364000     # 20ft out: C1

    # Drive (tee -> 200ft), tagged with the disc
    r = client.post(f"/rounds/{rid}/holes/{hid}/throws", json={
        "throw_number": 1, "disc_id": disc_id,
        "start_latitude": tee_lat, "start_longitude": -105.0,
        "end_latitude": drive_end, "end_longitude": -105.0
    })
    assert r.status_code == 200
    assert abs(r.json()["distance_ft"] - 200) <= 3

    # Approach (200ft -> 20ft out)
    client.post(f"/rounds/{rid}/holes/{hid}/throws", json={
        "throw_number": 2,
        "start_latitude": drive_end, "start_longitude": -105.0,
        "end_latitude": putt_start, "end_longitude": -105.0
    })
    # Holed putt from C1
    client.post(f"/rounds/{rid}/holes/{hid}/throws", json={
        "throw_number": 3, "is_holed": True,
        "start_latitude": putt_start, "start_longitude": -105.0,
        "end_latitude": basket_lat, "end_longitude": -105.0
    })

    stats = client.get(f"/rounds/{rid}/stats").json()
    assert stats["holes_with_throws"] == 1
    assert stats["c1_putts_attempted"] == 1
    assert stats["c1_putts_made"] == 1
    assert stats["fairway_attempts"] == 1
    assert stats["fairway_hits"] == 1

    # The tagged drive feeds disc stats (combined with the 1 seeded manual stat... 
    # manual upsert is replaced by sync): sample includes the round throw
    bag_stats = client.get("/bag/stats").json()
    disc_stat = next(s for s in bag_stats if s["disc_id"] == disc_id)
    assert disc_stat["sample_size"] >= 1


def test_delete_disc_with_stats_and_throws(client):
    """Deleting a disc that has stats and recorded throws must not 500."""
    cid, _ = seed_course(client)
    hid, _ = seed_mapped_hole(client, cid)
    disc_id = add_disc_with_stats(client, avg=300)
    rid = client.post("/rounds", json={"course_id": cid}).json()["round_id"]
    client.post(f"/rounds/{rid}/holes/{hid}/throws", json={
        "throw_number": 1, "disc_id": disc_id,
        "start_latitude": 40.0, "start_longitude": -105.0,
        "end_latitude": 40.0005, "end_longitude": -105.0
    })

    response = client.delete(f"/bag/discs/{disc_id}")
    assert response.status_code == 200
    assert client.get("/bag/discs").json() == []


def test_zone_based_throws_and_stats(client):
    """uDisc-style detailed scoring with no GPS: zones drive the stats."""
    cid, holes = seed_course(client)
    hid = holes[0]
    rid = client.post("/rounds", json={"course_id": cid}).json()["round_id"]

    # Drive lands in C1
    client.post(f"/rounds/{rid}/holes/{hid}/throws", json={
        "throw_number": 1, "landing_zone": "c1"
    })
    # Missed putt from C1, stays in C1
    client.post(f"/rounds/{rid}/holes/{hid}/throws", json={
        "throw_number": 2, "landing_zone": "c1", "putt_distance_ft": 27
    })
    # Holed putt from C1
    client.post(f"/rounds/{rid}/holes/{hid}/throws", json={
        "throw_number": 3, "landing_zone": "basket", "is_holed": True, "putt_distance_ft": 6
    })

    stats = client.get(f"/rounds/{rid}/stats").json()
    assert stats["fairway_attempts"] == 1
    assert stats["fairway_hits"] == 1       # C1 counts as hitting the fairway
    assert stats["c1_putts_attempted"] == 2  # throws 2 and 3 start from C1
    assert stats["c1_putts_made"] == 1


def test_ob_drop_zone_flow(client):
    """OB drive, drop in fairway, C2 approach, holed C2 putt."""
    cid, holes = seed_course(client)
    hid = holes[0]
    rid = client.post("/rounds", json={"course_id": cid}).json()["round_id"]

    client.post(f"/rounds/{rid}/holes/{hid}/throws", json={
        "throw_number": 1, "landing_zone": "ob", "drop_zone": "fairway"
    })
    client.post(f"/rounds/{rid}/holes/{hid}/throws", json={
        "throw_number": 2, "landing_zone": "c2"
    })
    client.post(f"/rounds/{rid}/holes/{hid}/throws", json={
        "throw_number": 3, "landing_zone": "basket", "is_holed": True
    })

    stats = client.get(f"/rounds/{rid}/stats").json()
    assert stats["fairway_attempts"] == 1
    assert stats["fairway_hits"] == 0       # OB drive missed
    assert stats["c2_putts_attempted"] == 1  # throw 3 starts from C2
    assert stats["c2_putts_made"] == 1
    assert stats["c1_putts_attempted"] == 0


def test_delete_round_throw(client):
    cid, holes = seed_course(client)
    hid = holes[0]
    rid = client.post("/rounds", json={"course_id": cid}).json()["round_id"]
    throw = client.post(f"/rounds/{rid}/holes/{hid}/throws", json={
        "throw_number": 1, "landing_zone": "ob"
    }).json()

    response = client.delete(f"/rounds/{rid}/throws/{throw['round_throw_id']}")
    assert response.status_code == 200
    assert client.get(f"/rounds/{rid}/stats").json()["fairway_attempts"] == 0


def test_round_setup_options(client):
    cid, _ = seed_course(client)
    round_ = client.post("/rounds", json={
        "course_id": cid, "tracking_mode": "detail", "layout": "front9"
    }).json()
    assert round_["tracking_mode"] == "detail"
    assert round_["layout"] == "front9"

    # Mode is changeable mid-round
    updated = client.patch(f"/rounds/{round_['round_id']}", json={"tracking_mode": "score"}).json()
    assert updated["tracking_mode"] == "score"

    # Invalid values rejected
    assert client.post("/rounds", json={"course_id": cid, "tracking_mode": "yolo"}).status_code == 400


def test_lifetime_stats_empty(client):
    """No rounds yet -> all zeros, and /rounds/stats resolves to the lifetime
    endpoint (not the /{round_id}/stats route)."""
    stats = client.get("/rounds/stats/lifetime").json()
    assert stats["rounds_played"] == 0
    assert stats["holes_with_throws"] == 0
    assert stats["c1_putts_attempted"] == 0
    assert stats["gir_attempts"] == 0


def test_lifetime_stats_aggregate(client):
    """Lifetime stats aggregate across rounds, including C1X and GIR."""
    cid, _ = seed_course(client)
    hid, _ = seed_mapped_hole(client, cid)  # par 3 -> regulation = 1 throw
    rid = client.post("/rounds", json={"course_id": cid}).json()["round_id"]

    tee_lat = 40.0
    basket_lat = 40.0 + 300 / 364000
    drive_end = 40.0 + 200 / 364000        # 200ft, in the corridor, short of the green
    putt_start = basket_lat - 20 / 364000  # 20ft out: C1, and outside the C1X gimme range

    client.post(f"/rounds/{rid}/holes/{hid}/throws", json={
        "throw_number": 1, "start_latitude": tee_lat, "start_longitude": -105.0,
        "end_latitude": drive_end, "end_longitude": -105.0})
    client.post(f"/rounds/{rid}/holes/{hid}/throws", json={
        "throw_number": 2, "start_latitude": drive_end, "start_longitude": -105.0,
        "end_latitude": putt_start, "end_longitude": -105.0})
    client.post(f"/rounds/{rid}/holes/{hid}/throws", json={
        "throw_number": 3, "is_holed": True,
        "start_latitude": putt_start, "start_longitude": -105.0,
        "end_latitude": basket_lat, "end_longitude": -105.0})

    stats = client.get("/rounds/stats/lifetime").json()
    assert stats["rounds_played"] == 1
    assert stats["holes_with_throws"] == 1
    assert stats["c1_putts_attempted"] == 1
    assert stats["c1_putts_made"] == 1
    assert stats["c1x_putts_attempted"] == 1  # 20ft putt is outside the 11ft gimme range
    assert stats["c1x_putts_made"] == 1
    assert stats["fairway_hits"] == 1
    assert stats["gir_attempts"] == 1
    # Green reached on throw 2, but par-3 regulation is 1 throw -> not in reg
    assert stats["gir_c1"] == 0
