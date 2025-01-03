from flask import Blueprint, request

from api import account_api

account_blueprint = Blueprint('account', __name__)

@account_blueprint.route("/create-account", methods=['POST'])
def create_account():
    username = request.form.get("nm")
    if Account.name_exists(username):
        return redirect("/account/create")

    password = request.form.get("pw")
    email = request.form.get("em")
    try:
        osuid = int(request.form.get("id"))
    except:
        osuid = 0
    about_me = request.form.get("am")
    account_api.account_create(username, password, email, osuid, about_me)
    login_result = account_api.login(username, password)
    if login_result != "incorrect info" and login_result is not None:
        resp = make_response(
            render_template('account/user-profile.html',
                            account=login_result
                            ))
        resp.set_cookie('userID', str(login_result["id"]))
        return resp
    else:
        resp = make_response(
            render_template('account/login.html', warning="incorrect info"))
        return resp