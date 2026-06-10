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


def test_list_users(client):
    users = client.get("/auth/users").json()
    assert len(users) == 1
    assert users[0]["user_id"] == 1


def test_toggle_admin_on_other_user(client):
    from tests.conftest import TestingSessionLocal
    from app.models import User

    db = TestingSessionLocal()
    db.add(User(user_id=2, email="other@test.com", google_id="g2", name="Other"))
    db.commit()
    db.close()

    promoted = client.patch("/auth/users/2", json={"is_admin": True}).json()
    assert promoted["is_admin"] is True
    demoted = client.patch("/auth/users/2", json={"is_admin": False}).json()
    assert demoted["is_admin"] is False


def test_cannot_demote_self(client):
    assert client.patch("/auth/users/1", json={"is_admin": False}).status_code == 400


def test_unknown_user_404(client):
    assert client.patch("/auth/users/99", json={"is_admin": True}).status_code == 404
