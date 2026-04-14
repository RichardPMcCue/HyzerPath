from unittest.mock import patch, AsyncMock, MagicMock

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

@patch("app.routers.bag.httpx.AsyncClient")
def test_search_discs(mock_client, client):
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = [
        {
            "id": "b61c0b30-f06b-5f66-a567-78287b003869",
            "name": "Buzzz",
            "brand": "Discraft",
            "category": "Midrange",
            "speed": "5",
            "glide": "4",
            "turn": "-1",
            "fade": "1",
            "stability": "Stable",
            "link": "https://www.marshallstreetdiscgolf.com/?s=buzzz&post_type=product",
            "pic": "https://s3.amazonaws.com/media.marshallstreetdiscgolf.com/inbounds/2380596.webp",
            "name_slug": "buzzz",
            "brand_slug": "discraft",
            "category_slug": "midrange",
            "stability_slug": "stable",
            "color": "#FF3737",
            "background_color": "#000000",
        }
    ]
    mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

    response = client.get("/bag/discs/search?name=buzzz&brand=discraft")

    assert response.status_code == 200
    discs = response.json()
    assert len(discs) == 1
    assert discs[0]["name"] == "Buzzz"
    assert discs[0]["disc_type"] == "midrange"