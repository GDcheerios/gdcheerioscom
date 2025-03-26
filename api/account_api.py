from flask_bcrypt import Bcrypt

import environment
from objects.Account import Account


def account_create(username, password, email, osu_id=0, about_me=""):
    """
    Create a new account.
    """

    password = str(password)
    password = str(environment.bcrypt.generate_password_hash(password))[2:-1]  # remove the byte chars

    Account.create(username, password, email, osu_id, about_me)


def login(username, password) -> tuple[dict, int]:
    """
    Checks a user's credentials and returns the account if they are correct.

    :param username: The username of the account to check.
    :param password: The password of the account to check.
    :return: Account information if the credentials are correct, 0 if the account doesn't exist, 1 if the credentials are incorrect.
    """

    account = Account(username)
    if account.exists:
        if environment.bcrypt.check_password_hash(account.password, password):
            return {
                "success": True,
                "data": account.jsonify()
            }, 200

        return {
            "success": False,
            "error": "wrong_password"
        }, 401

    return {
        "success": False,
        "error": "account_not_found"
    }, 404
