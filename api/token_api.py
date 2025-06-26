import secrets
from PSQLConnector import PSQLConnection as db


def generate_token():
    """
    Generate a new token and insert it into the database
    :return: str, the generated token
    """

    token = secrets.token_urlsafe(32)  # we generate an url safe 32 char long token
    db.execute("INSERT INTO tokens values (%s);", params=(token,))
    return token


def clear_tokens():
    """
    delete all tokens from the database

    :return: str, "done"
    """

    db.execute("DELETE FROM tokens *;")
    return "done"


def delete_token(token):
    """
    remove a token from the database

    :param token: str, the token to remove
    :return: str, the removed token
    """

    db.execute("DELETE FROM tokens WHERE token = %s;", params=(token,))
    return token


def verify_token(token):
    """
    verify if a token exists in the database

    :param token: str, the token to verify
    :return: true or false, depending on if the token exists in the database
    """

    result = db.fetch_one("SELECT * FROM tokens where value = %s;", params=(token,))
    return str(result is not None)
