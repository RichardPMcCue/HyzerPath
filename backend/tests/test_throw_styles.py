import math
from types import SimpleNamespace

from app.fairway import FairwayRegion
from app.recommendation import recommend_route, style_finishes_left

LAT0, LNG0 = 40.0, -90.0
LNG_FT = 364000.0 * math.cos(math.radians(LAT0))


def ll(x_ft, y_ft):
    return (LAT0 + y_ft / 364000.0, LNG0 + x_ft / LNG_FT)


def right_dogleg():
    """250ft north then 250ft east, in a 60ft-wide L-shaped fairway. The
    derived route turns hard right at the corner."""
    ring = [ll(-30, 0), ll(30, 0), ll(30, 220), ll(280, 220), ll(280, 280), ll(-30, 280)]
    region = FairwayRegion(ring)
    route = region.route(ll(0, 5), ll(250, 250), erosion_ft=15)
    return region, route


def _disc(disc_id, name, speed, turn, fade):
    return SimpleNamespace(
        disc_id=disc_id, name=name, manufacturer="Test",
        speed=speed, glide=5.0, turn=turn, fade=fade,
    )


def test_style_finishes_left():
    assert style_finishes_left("right", "backhand") is True
    assert style_finishes_left("right", "forehand") is False
    assert style_finishes_left("left", "backhand") is False
    assert style_finishes_left("left", "forehand") is True


def test_forehand_chosen_for_right_dogleg():
    """Hole bends hard RIGHT. For a righty, the forehand fade finishes right —
    with equal distances both styles available, the FH should win the corner."""
    region, route = right_dogleg()
    disc = _disc(1, "Stable", 9.0, 0.0, 2.0)  # fades toward its style's side

    recs = recommend_route(
        region=region,
        route=route,
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
    region, route = right_dogleg()
    disc = _disc(1, "Stable", 9.0, 0.0, 2.0)

    recs = recommend_route(
        region=region,
        route=route,
        discs=[disc],
        disc_distances={1: 260},
        style_distances={"backhand": {1: 260}},  # no forehand data
        hand="right",
    )
    assert all(r.throw_style == "backhand" for r in recs)


def test_short_forehand_not_picked_beyond_its_range():
    """FH only carries 150 ft — a 250 ft right-bending throw should still
    fall back to the backhand (flex) rather than an underthrown forehand."""
    region, route = right_dogleg()
    discs = [_disc(1, "Stable", 9.0, 0.0, 2.0), _disc(2, "Flippy", 9.0, -3.0, 1.0)]

    recs = recommend_route(
        region=region,
        route=route,
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


def test_throw_style_profile_roundtrip(client):
    rows = client.put("/auth/me/throw-styles", json=[
        {"throw_type": "backhand", "hand": "right", "priority": 1},
        {"throw_type": "forehand", "hand": "right", "priority": 2}
    ]).json()
    assert len(rows) == 2
    assert client.get("/auth/me/throw-styles").json()[0]["throw_type"] == "backhand"

    # replace with FH-only lefty
    rows = client.put("/auth/me/throw-styles", json=[
        {"throw_type": "forehand", "hand": "left", "priority": 1}
    ]).json()
    assert rows == [{"throw_type": "forehand", "hand": "left", "priority": 1}]


def test_throw_style_profile_validation(client):
    assert client.put("/auth/me/throw-styles", json=[]).status_code == 400
    assert client.put("/auth/me/throw-styles", json=[
        {"throw_type": "sidearm", "hand": "right", "priority": 1}
    ]).status_code == 400
    assert client.put("/auth/me/throw-styles", json=[
        {"throw_type": "backhand", "hand": "right", "priority": 1},
        {"throw_type": "backhand", "hand": "left", "priority": 2}
    ]).status_code == 400


def test_disabled_style_never_recommended():
    region, route = right_dogleg()
    disc = _disc(1, "Stable", 9.0, 0.0, 2.0)

    # FH data exists and fits the right dogleg, but the profile is BH-only
    recs = recommend_route(
        region=region,
        route=route,
        discs=[disc],
        disc_distances={1: 260},
        style_distances={"backhand": {1: 260}, "forehand": {1: 260}},
        hand="right",
        allowed_styles=["backhand"],
    )
    assert all(r.throw_style == "backhand" for r in recs)


def test_lefty_backhand_owns_right_dogleg():
    """LHBH fades right — a right-bending hole is hyzer territory for a lefty
    backhand, no forehand needed."""
    region, route = right_dogleg()
    disc = _disc(1, "Stable", 9.0, 0.0, 2.0)

    recs = recommend_route(
        region=region,
        route=route,
        discs=[disc],
        disc_distances={1: 260},
        style_distances={"backhand": {1: 260}},
        hand="left",
        style_hands={"backhand": "left"},
        allowed_styles=["backhand"],
    )
    assert recs[0].throw_style == "backhand"
    assert recs[0].shot_shape in ("hyzer", "spike_hyzer")
