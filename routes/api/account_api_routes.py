import hashlib
from datetime import datetime, timedelta
from flask import Blueprint, request, redirect, make_response, render_template, Response

import environment
from api import account_api
from objects.Account import Account

account_api_blueprint = Blueprint('account', __name__)


@account_api_blueprint.post("/account/create-account")
def create_account() -> Response:
    """
    The account creation POST method.
    This method handles the information sent from the create account form
    to create an account.
    """

    username = request.form.get("nm")
    if Account.name_exists(username):
        return redirect("/account/create")

    password = request.form.get("pw")
    email = request.form.get("em")
    about_me = request.form.get("am")

    supporter_id = request.args.get("supporter_id")

    result = Account.queue(username, password, email, 0, about_me, supporter_id)

    return redirect(f"/account/create?msg={result['message']}")


@account_api_blueprint.post('/account/login-form')
def login_cookie():
    """
    Login form POST method.
    Handles the login form POST request and creates a cookie with the user's ID'.
    """

    username = request.form.get('nm')
    password = request.form.get('pw')
    supporter_id = request.form.get("supporter_id")
    login_result = account_api.login(username, password)
    if login_result[1] == 404:
        resp = make_response(
            render_template('account/login.html', warning="Couldn't find account with that username.", code=401))
    elif login_result[1] == 401:
        resp = make_response(
            render_template('account/login.html', warning="Incorrect password.", code=404))
    else:
        if supporter_id is not None:
            Account.claim_supporter(supporter_id, login_result[0]['data']['id'])
        account = login_result[0]['data']  # set this to only read login data
        resp = make_response(redirect(f"/account/{account['id']}"))
        resp.set_cookie('session', str(login_result[0]['session_id']), expires=datetime.now() + timedelta(days=360))
        return resp

    return resp


@account_api_blueprint.post("/account/login-json")
def login_json():
    username = request.json["username"]
    password = request.json["password"]

    login_result = account_api.login(username, password)
    return login_result


@account_api_blueprint.route("/account/verify")
def verify_account() -> Response:
    sid = request.args.get("sid")
    token = request.args.get("token")

    if not sid or not token:
        return Response(status=400)

    row = environment.database.fetch_to_dict(
        "SELECT id, email, username, password, osu_id, about, token, expires, supporter_id FROM pending_accounts WHERE id = %s",
        params=(sid,)
    )
    if not row:
        return redirect("/account/create?msg=invalid or used")

    environment.database.execute(
        """
        DELETE
        FROM pending_accounts
        WHERE expires < NOW()
          OR id = %s
        """,
        params=(sid,)
    )

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    if row["token"] != token_hash:
        return redirect("/account/create?msg=invalid token")

    if Account.name_exists(row["username"]):
        return redirect("/account/create?msg=username taken")

    account = Account.create(
        row["username"],
        row["password"],
        row["email"],
        row["osu_id"],
        row["about"]
    )

    if row["supporter_id"] is not None:
        Account.claim_supporter(row["supporter_id"], account.id)

    resp = make_response(redirect(f"/account/{account.id}"))
    resp.set_cookie('session', str(Account.create_session(account.id)), expires=datetime.now() + timedelta(days=360))
    return resp


@account_api_blueprint.route("/account/signout")
def signout():
    resp = make_response(render_template('account/login.html'))
    resp.delete_cookie('session')
    return resp


@account_api_blueprint.post("/account/change-username")
def change_username():
    id = Account.id_from_session(request.cookies.get("session"))
    account = Account(id)
    username = request.form.get("username")
    if not Account.name_exists(username):
        Account.change_username(int(id), username)

    return redirect(f'/user/{account.id}')


@account_api_blueprint.post("/account/change-about")
def change_about():
    id = Account.id_from_session(request.cookies.get("session"))
    account = Account(id)
    about_me = request.form.get("about_me")
    Account.change_about(int(id), about_me)

    return redirect(f'/user/{account.id}')


@account_api_blueprint.get("/account/check/username")
def check_username():
    username = request.args.get("username")
    return {"exists": Account.name_exists(username)}


@account_api_blueprint.get("/account/check/email")
def check_email():
    email = request.args.get("email")
    print(email, Account.email_exists(email))
    return {"exists": Account.email_exists(email)}


@account_api_blueprint.get("/account/grab/<identifier>")
def grab_account(identifier):
    return Account(identifier).jsonify()


@account_api_blueprint.post("/account/set-osu")
def set_osu():
    id = request.form["osu_id"]
    user_id = Account.id_from_session(request.cookies.get("session"))
    if user_id:
        user = Account(user_id)
        user.set_osu_id(id)
        return redirect(f"/user/{user_id}")

    return redirect(f"/user/{user_id}")

