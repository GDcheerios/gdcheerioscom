import pytest

from main import create_app
import environment as env

env.email_verification = False


@pytest.fixture(scope="session")
def app():
    app = create_app()

    yield app


@pytest.fixture(scope="session")
def environment():
    return env


@pytest.fixture(scope="session")
def db():
    return env.database


@pytest.fixture(scope="function")
def client(app):
    return app.test_client()


@pytest.fixture(scope="function")
def runner(app):
    return app.test_cli_runner()
