from types import SimpleNamespace

from app.recommendation import recommend_path, style_finishes_left


def test_style_finishes_left():
    assert style_finishes_left("right", "backhand") is True
    assert style_finishes_left("right", "forehand") is False
    assert style_finishes_left("left", "backhand") is False
    assert style_finishes_left("left", "forehand") is True


def _node(node_id, lat, lng):
    return SimpleNamespace(
        hole_node_id=node_id, latitude=lat, longitude=lng,
        node_type="landing_zone", sequence=node_id, is_fairway=True,
    )


def _edge(a, b, dist):
    return SimpleNamespace(
        hole_edge_id=0, from_node_id=a, to_node_id=b,
        distance=dist, fairway_width=None, edge_hazards=[],
    )


def _disc(disc_id, name, speed, turn, fade):
    return SimpleNamespace(
        disc_id=disc_id, name=name, manufacturer="Test",
        speed=speed, glide=5.0, turn=turn, fade=fade,
    )


def test_forehand_chosen_for_right_dogleg():
    """Hole bends hard RIGHT. For a righty, the forehand fade finishes right —
    with equal distances both styles available, the FH should win the corner."""
    # tee → corner (north 250ft) → basket (east 250ft): finish bends right ~90°
    nodes = [
        _node(1, 40.0, -90.0),
        _node(2, 40.000687, -90.0),       # 250 ft north
        _node(3, 40.000687, -89.999103),  # 250 ft east
    ]
    edges = {
        (1, 2): _edge(1, 2, 250),
        (2, 3): _edge(2, 3, 250),
    }
    disc = _disc(1, "Stable", 9.0, 0.0, 2.0)  # fades toward its style's side

    recs = recommend_path(
        path_nodes=nodes,
        edge_lookup=edges,
        discs=[disc],
        disc_distances={1: 260},
        style_distances={"backhand": {1: 260}, "forehand": {1: 260}},
        hand="right",
        mode="balanced",
    )
    assert len(recs) == 2
    # First throw must finish right (toward the corner) — forehand territory
    assert recs[0].throw_style == "forehand"
    assert recs[0].shot_shape in ("hyzer", "spike_hyzer")


def test_backhand_only_player_never_gets_forehand(client=None):
    nodes = [
        _node(1, 40.0, -90.0),
        _node(2, 40.000687, -90.0),
        _node(3, 40.000687, -89.999103),
    ]
    edges = {(1, 2): _edge(1, 2, 250), (2, 3): _edge(2, 3, 250)}
    disc = _disc(1, "Stable", 9.0, 0.0, 2.0)

    recs = recommend_path(
        path_nodes=nodes,
        edge_lookup=edges,
        discs=[disc],
        disc_distances={1: 260},
        style_distances={"backhand": {1: 260}},  # no forehand data
        hand="right",
    )
    assert all(r.throw_style == "backhand" for r in recs)


def test_short_forehand_not_picked_beyond_its_range():
    """FH only carries 150 ft — a 250 ft right-bending throw should still
    fall back to the backhand (flex) rather than an underthrown forehand."""
    nodes = [
        _node(1, 40.0, -90.0),
        _node(2, 40.000687, -90.0),
        _node(3, 40.000687, -89.999103),
    ]
    edges = {(1, 2): _edge(1, 2, 250), (2, 3): _edge(2, 3, 250)}
    discs = [_disc(1, "Stable", 9.0, 0.0, 2.0), _disc(2, "Flippy", 9.0, -3.0, 1.0)]

    recs = recommend_path(
        path_nodes=nodes,
        edge_lookup=edges,
        discs=discs,
        disc_distances={1: 260, 2: 260},
        style_distances={
            "backhand": {1: 260, 2: 260},
            "forehand": {1: 150, 2: 150},
        },
        hand="right",
    )
    assert recs[0].throw_style == "backhand"


def test_measure_throw_with_style_splits_stats(client):
    disc_id = client.post("/bag/discs", json={
        "name": "Buzzz", "manufacturer": "Discraft", "disc_type": "midrange"
    }).json()["disc_id"]
    session_id = client.post("/throws/sessions", json={
        "start_latitude": 40.0, "start_longitude": -90.0
    }).json()["session_id"]

    # ~250 ft backhand, ~150 ft forehand
    client.post(f"/throws/sessions/{session_id}/throws", json={
        "end_latitude": 40.000687, "end_longitude": -90.0,
        "disc_id": disc_id, "throw_style": "backhand"
    })
    client.post(f"/throws/sessions/{session_id}/throws", json={
        "end_latitude": 40.000412, "end_longitude": -90.0,
        "disc_id": disc_id, "throw_style": "forehand"
    })

    stats = client.get("/bag/stats").json()
    by_style = {s["throw_style"]: s for s in stats if s["disc_id"] == disc_id}
    assert set(by_style) == {"backhand", "forehand"}
    assert by_style["backhand"]["avg_distance"] > by_style["forehand"]["avg_distance"]


def test_manual_stat_upsert_per_style(client):
    disc_id = client.post("/bag/discs", json={
        "name": "Destroyer", "manufacturer": "Innova", "disc_type": "distance_driver"
    }).json()["disc_id"]

    client.put(f"/bag/discs/{disc_id}/stats", json={
        "avg_distance": 380, "throw_style": "backhand"
    })
    client.put(f"/bag/discs/{disc_id}/stats", json={
        "avg_distance": 280, "throw_style": "forehand"
    })

    stats = [s for s in client.get("/bag/stats").json() if s["disc_id"] == disc_id]
    assert len(stats) == 2
    assert client.put(f"/bag/discs/{disc_id}/stats", json={
        "avg_distance": 300, "throw_style": "sidearm"
    }).status_code == 400
