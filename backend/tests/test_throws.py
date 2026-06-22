import pytest

# ~364,000 ft per degree of latitude; 300 ft ≈ 0.000824 degrees
FT_300_IN_LAT = 300 / 364000.0


def make_session(client, lat=40.0, lon=-105.0, label="Field work"):
    response = client.post("/throws/sessions", json={
        "start_latitude": lat,
        "start_longitude": lon,
        "label": label
    })
    assert response.status_code == 200
    return response.json()


def make_disc(client, name="Destroyer"):
    response = client.post("/bag/discs", json={
        "name": name,
        "manufacturer": "Innova",
        "disc_type": "distance_driver"
    })
    return response.json()["disc_id"]


def test_create_session_and_measure_throw(client):
    session = make_session(client)

    response = client.post(f"/throws/sessions/{session['session_id']}/throws", json={
        "end_latitude": 40.0 + FT_300_IN_LAT,
        "end_longitude": -105.0
    })
    assert response.status_code == 200
    throw = response.json()
    assert throw["distance_ft"] == pytest.approx(300, rel=0.02)


def test_multiple_throws_reuse_same_start(client):
    """The session keeps the start point; each throw only needs an end point."""
    session = make_session(client)
    sid = session["session_id"]

    for i, dist_ft in enumerate([250, 300, 350]):
        response = client.post(f"/throws/sessions/{sid}/throws", json={
            "end_latitude": 40.0 + dist_ft / 364000.0,
            "end_longitude": -105.0
        })
        assert response.status_code == 200

    response = client.get(f"/throws/sessions/{sid}")
    throws = response.json()["throws"]
    assert len(throws) == 3
    distances = sorted(t["distance_ft"] for t in throws)
    assert distances[0] == pytest.approx(250, rel=0.02)
    assert distances[2] == pytest.approx(350, rel=0.02)


def test_throw_with_disc_syncs_disc_stats(client):
    """Measured throws tagged with a disc feed the recommendation engine."""
    disc_id = make_disc(client)
    session = make_session(client)
    sid = session["session_id"]

    for dist_ft in [280, 320]:
        client.post(f"/throws/sessions/{sid}/throws", json={
            "end_latitude": 40.0 + dist_ft / 364000.0,
            "end_longitude": -105.0,
            "disc_id": disc_id
        })

    stats = client.get("/bag/stats").json()
    assert len(stats) == 1
    assert stats[0]["disc_id"] == disc_id
    assert stats[0]["avg_distance"] == pytest.approx(300, rel=0.02)
    assert stats[0]["max_distance"] == pytest.approx(320, rel=0.02)
    assert stats[0]["sample_size"] == 2


def test_delete_throw_resyncs_stats(client):
    disc_id = make_disc(client)
    session = make_session(client)
    sid = session["session_id"]

    client.post(f"/throws/sessions/{sid}/throws", json={
        "end_latitude": 40.0 + 280 / 364000.0, "end_longitude": -105.0, "disc_id": disc_id
    })
    long_throw = client.post(f"/throws/sessions/{sid}/throws", json={
        "end_latitude": 40.0 + 400 / 364000.0, "end_longitude": -105.0, "disc_id": disc_id
    }).json()

    client.delete(f"/throws/sessions/{sid}/throws/{long_throw['throw_id']}")

    stats = client.get("/bag/stats").json()
    assert stats[0]["sample_size"] == 1
    assert stats[0]["max_distance"] == pytest.approx(280, rel=0.02)



def test_throw_with_unknown_disc_404(client):
    session = make_session(client)
    response = client.post(f"/throws/sessions/{session['session_id']}/throws", json={
        "end_latitude": 40.001, "end_longitude": -105.0, "disc_id": 9999
    })
    assert response.status_code == 404


def test_unknown_session_404(client):
    response = client.post("/throws/sessions/9999/throws", json={
        "end_latitude": 40.001, "end_longitude": -105.0
    })
    assert response.status_code == 404


def test_delete_session_cascades(client):
    session = make_session(client)
    sid = session["session_id"]
    client.post(f"/throws/sessions/{sid}/throws", json={
        "end_latitude": 40.001, "end_longitude": -105.0
    })

    response = client.delete(f"/throws/sessions/{sid}")
    assert response.status_code == 200
    assert client.get(f"/throws/sessions/{sid}").status_code == 404
