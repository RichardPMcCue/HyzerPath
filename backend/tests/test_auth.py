def test_get_me(client):
    me = client.get("/auth/me").json()
    assert me["user_id"] == 1
    assert me["email"] == "test@test.com"
    assert me["is_admin"] is True
    assert me["username"] is None


def test_set_username(client):
    me = client.patch("/auth/me", json={"username": "ricky"}).json()
    assert me["username"] == "ricky"
    assert client.get("/auth/me").json()["username"] == "ricky"


def test_username_validation(client):
    assert client.patch("/auth/me", json={"username": "x"}).status_code == 400
    assert client.patch("/auth/me", json={"username": "x" * 31}).status_code == 400
