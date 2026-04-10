def test_create_disc(client):
    response = client.post("/bag/discs", json={
        "name": "Buzzz",
        "manufacturer": "Discraft",
        "disc_type": "midrange",
        "speed": 5.0,
        "glide": 4.0,
        "turn": -1.0,
        "fade": 1.0,
        "wear": 1.0,
        "weight": 177
    })
    assert response.status_code == 200
    assert response.json()["name"] == "Buzzz"

def test_get_disc(client):
    create = client.post("/bag/discs", json={
        "name": "Buzzz",
        "manufacturer": "Discraft",
        "disc_type": "midrange"
    })
    disc_id = create.json()["disc_id"]

    response = client.get(f"/bag/discs/{disc_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Buzzz"

def test_delete_disc(client):
    create = client.post("/bag/discs", json={
        "name": "Buzzz",
        "manufacturer": "Discraft",
        "disc_type": "midrange"
    })
    disc_id = create.json()["disc_id"]

    response = client.delete(f"/bag/discs/{disc_id}")
    assert response.status_code == 200
    assert response.json()["message"] == "Disc deleted"
