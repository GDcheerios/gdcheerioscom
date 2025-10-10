import json
from flask import Blueprint, render_template, make_response, request, redirect

import environment
from objects import Account

account_blueprint = Blueprint("account_blueprint", __name__)


@account_blueprint.route("/")
def account():
    id = request.cookies.get("userID")
    if id is None:
        return redirect("/account/login")
    else:
        return redirect(f"/account/{id}")


@account_blueprint.route("/<id>")
def user(id: int | str): return render_template("account/user-profile.html", account=Account(id))


@account_blueprint.route("/create")
def create():
    osu_info = request.args.get("osu_info")
    if osu_info is not None:
        osu_info = json.loads(osu_info)
    return render_template("account/create.html",
                           client_id=environment.osu_client_id,
                           redirect_uri=f"{environment.domain}/api/code_grab",
                           osu_info=osu_info,
                           msg=request.args.get("msg")
                           )


@account_blueprint.route("/login")
def login(): return render_template("account/login.html")


@account_blueprint.route("/signout")
def signout():
    resp = make_response(redirect('/account/login'))
    resp.delete_cookie('userID')
    return resp
