from flask_bcrypt import Bcrypt

from crap.Account import Account


def account_create(username, password, email, osu_id=0, about_me=""):
    password = str(password)
    password = str(Bcrypt.generate_password_hash(password))[2:-1]

    Account.create(username, password, email, osu_id, about_me)


def login(username, password) -> str | dict:
    account = Account(username)
    if account:
        if Bcrypt.check_password_hash(account.password, password):
            return account.jsonify()

    return "incorrect info"
