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
    if login_result != "false" and login_result is not None:
        resp = make_response(
            render_template(
                'account/user-profile.html',
                account=login_result
            )
        )

        resp.set_cookie('userID', str(login_result["id"]))

    else:
        resp = make_response(
            render_template(
                'account/create.html'
            )
        )

    return resp


@account_api_blueprint.route('/account/login-form', methods=['POST'])
async def login_cookie():
    """
    Login form POST method.
    Handles the login form POST request and creates a cookie with the user's ID'.
    """

    username = request.form.get('nm')
    password = request.form.get('pw')
    login_result = account_api.login(username, password)
    if login_result == 0:
        resp = make_response(
            render_template('account/login.html', warning="Couldn't find account with that username."))
    elif login_result == 1:
        resp = make_response(
            render_template('account/login.html', warning="Incorrect password."))
    else:
        resp = make_response(redirect(f'/account/{login_result["id"]}'))
        resp.set_cookie('userID', str(login_result["id"]), expires=datetime.now() + timedelta(days=360))
        return resp

    return resp


@account_api_blueprint.route("/account/login-json", methods=['POST'])
async def login_json():
    username = request.json["username"]
    password = request.json["password"]

    login_result = account_api.login(username, password)
    if login_result != "incorrect info" and login_result is not None:
        return login_result


@account_api_blueprint.route("/account/signout")
async def signout():
    resp = make_response(render_template('account/login.html'))
    resp.delete_cookie('userID')
    return resp


@account_api_blueprint.route("/api/account/change-username", methods=["POST"])
async def change_username():
    id = request.cookies.get("userID")
    account = Account(id)
    username = request.form.get("username")
    if not Account.name_exists(username):
        Account.change_username(int(id), username)

    return redirect(f'/user/{account.id}')


@account_api_blueprint.route("/api/account/grab/<identifier>")
async def grab_account(identifier):
    return Account(identifier).jsonify()
