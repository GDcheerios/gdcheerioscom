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

        Account.from_session(client.get_cookie("session").value).delete()

    def test_create_account_with_extras(self, client, db):
        supporter_id = db.fetch_one("insert into account.supports select from generate_series(1, 1) returning id")[0]

        form = {"nm": "test", "pw": "1234", "em": "test@example.com", "am": "Dude I'm testing so hard rn", "supporter_id": supporter_id, "osu_id": 11339405}

        response = client.post("/api/account/create-account", data=form)

        assert response.status_code == 302
        assert client.get_cookie("session") is not None

        account = Account.from_session(client.get_cookie("session").value)

        assert account.supporter is True
        assert account.get_osu_data()["id"] == 11339405

        account.delete()

    def test_signout(self, client):
        """
        Test logging out.
        """

        client.set_cookie("session", "")
        assert client.get_cookie("session") is not None

        response = client.get("/api/account/signout")

        assert response.status_code == 200
        assert client.get_cookie("session") is None

    def test_login_form(self, client):
        """
        Test logging in.
        """

        account = Account.create("test", Account.get_password_hash("1234"), email="test@example.com", about="")

        response = client.post("/api/account/login-form", data={"nm": "test", "pw": "1234"})

        assert response.status_code == 302
        assert client.get_cookie("session") is not None

        account.delete()

    def test_login_json(self, client):
        """
        Test logging in with JSON.
        """

        account = Account.create("test", Account.get_password_hash("1234"), email="test@example.com", about="")

        response = client.post("/api/account/login-json", json={"username": "test", "password": "1234"})

        assert response.status_code == 200

        account.delete()

    def test_claim_supporter(self, client, db):
        """
        Test claiming supporter.
        """

        account = Account.create("test", Account.get_password_hash("1234"), email="test@example.com", about="")
        session_id = account.create_session(account.id)
        client.set_cookie("session", session_id)
        supporter_id = db.fetch_one("insert into account.supports select from generate_series(1, 1) returning id")[0]
        response = client.get(f"/supporter/claim/{supporter_id}")

        assert response.status_code == 302
        assert account.is_supporter

        account.delete()

    def test_claim_supporter_on_login(self, client, db):
        """
        Test claiming supporter when already logged in.
        """

        account = Account.create("test", Account.get_password_hash("1234"), email="test@example.com", about="")
        supporter_id = db.fetch_one("insert into account.supports select from generate_series(1, 1) returning id")[0]
        response = client.post(f"/api/account/login-form", data={"nm": "test", "pw": "1234", "supporter_id": supporter_id})

        assert response.status_code == 302

        account.delete()

    def test_claim_supporter_taken(self, client, db):
        """
        Test claiming supporter when already claimed.
        """

        supporter_id = db.fetch_one("insert into account.supports (user_id) values (1) returning id")[0]
        response = client.post(f"/supporter/claim/{supporter_id}")

        assert response.status_code == 405
