import environment
from objects.Account import Account


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


def get_account_count() -> int:
    return environment.database.fetch_one("SELECT COUNT(*) FROM accounts")[0]
