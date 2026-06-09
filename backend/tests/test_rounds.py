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
