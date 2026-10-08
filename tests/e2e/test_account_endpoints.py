import pytest
from objects.Account import Account


@pytest.mark.slow
class TestAccountEndpoints:
    """
    Test cases for the account endpoints.
    """

    def test_create_account(self, client):
        """
        Test creating a new account.
        """

        form = {"nm": "test", "pw": "1234", "em": "test@example.com", "am": "Dude I'm testing so hard rn"}

        response = client.post("/api/account/create-account", data=form)

        assert response.status_code == 302
        assert client.get_cookie("session") is not None

    def test_create_account_with_extras(self, client, db):
        supporter_id = db.fetch_one("insert into account.supports select from generate_series(1, 1) returning id")[0]

        form = {"nm": "test2", "pw": "1234", "em": "test2@example.com", "am": "Dude I'm testing so hard rn", "supporter_id": supporter_id, "osu_id": 11339405}

        response = client.post("/api/account/create-account", data=form)
        print(response.json())
        account = Account.from_session(client.get_cookie("session"))

        assert response.status_code == 302
        assert client.get_cookie("session") is not None
        assert account.supporter is True
        assert account.osu_id == 11339405

    def test_signout(self, client):
        """
        Test logging out.
        """

        response = client.get("/api/account/signout")

        assert response.status_code == 200
        assert client.get_cookie("session") is None

    def test_login_form(self, client):
        """
        Test logging in.
        """

        response = client.post("/api/account/login-form", data={"username": "test", "password": "1234"})

        assert response.status_code == 302
        assert "session" in client._cookies
        assert Account.from_session(client.get_cookie("session")).id is not None

    def test_login_json(self, client):
        """
        Test logging in with JSON.
        """

        response = client.post("/api/account/login-json", json={"username": "test2", "password": "1234"})

        assert response.status_code == 200
        assert client.get_cookie("session") is not None
        assert Account.from_session(client.get_cookie("session")).id is not None
