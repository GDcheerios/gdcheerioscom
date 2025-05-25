from datetime import datetime, timedelta
from flask import Blueprint, request, redirect, make_response, render_template, Response

from api import account_api
from objects.Account import Account

account_api_blueprint = Blueprint('account', __name__)


@account_api_blueprint.route("/create-account", methods=['POST'])
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

    try:
        osu_id = int(request.form.get("id"))
    except ValueError:
        osu_id = 0

    about_me = request.form.get("am")
    account_api.account_create(username, password, email, osu_id, about_me)
    login_result = account_api.login(username, password)

    # Check if the user could be created
    if login_result[1] == 200:
        resp = make_response(
            redirect(
                '/account'
            )
        )

        resp.set_cookie('userID', str(login_result[0]['data']["id"]))

    else:
        error = ""
        if login_result[1] == 404:
            error = "Couldn't find account with that username."
        elif login_result[1] == 401:
            error = "Incorrect password."

        resp = make_response(
            render_template(
                'account/create.html', warning=error
            )
        )

    return resp


@account_api_blueprint.route('/account/login-form', methods=['POST'])
def login_cookie():
    """
    Login form POST method.
    Handles the login form POST request and creates a cookie with the user's ID'.
    """

    username = request.form.get('nm')
    password = request.form.get('pw')
    login_result = account_api.login(username, password)
    if login_result[1] == 404:
        resp = make_response(
            render_template('account/login.html', warning="Couldn't find account with that username.", code=401))
    elif login_result[1] == 401:
        resp = make_response(
            render_template('account/login.html', warning="Incorrect password.", code=404))
    else:
        account = login_result[0]['data']  # set this to only read login data
        resp = make_response(redirect(f"/account/{account['id']}"))
        resp.set_cookie('userID', str(account['id']), expires=datetime.now() + timedelta(days=360))
        return resp

    return resp


@account_api_blueprint.route("/account/login-json", methods=['POST'])
def login_json():
    username = request.json["username"]
    password = request.json["password"]

    login_result = account_api.login(username, password)
    return login_result


@account_api_blueprint.route("/account/signout")
def signout():
    resp = make_response(render_template('account/login.html'))
    resp.delete_cookie('userID')
    return resp


@account_api_blueprint.route("/account/change-username", methods=["POST"])
def change_username():
    id = request.cookies.get("userID")
    account = Account(id)
    username = request.form.get("username")
    if not Account.name_exists(username):
        Account.change_username(int(id), username)

    return redirect(f'/user/{account.id}')


@account_api_blueprint.route("/account/grab/<identifier>")
def grab_account(identifier):
    return Account(identifier).jsonify()
