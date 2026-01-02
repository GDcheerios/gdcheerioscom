from flask import Blueprint, render_template, redirect, request

import environment
from api.gentrys_quest.leaderboard_api import *

main_blueprint = Blueprint("main_blueprint", __name__)


# region Routes
@main_blueprint.route("/")
def index(): return render_template("index.html")


@main_blueprint.route("/about")
def about(): return render_template("about.html")


@main_blueprint.route("/supporter")
def supporter(): return render_template("supporter.html")


@main_blueprint.route("/supporter/claim/<id>")
def supporter_claim(id):
    session_id = request.cookies.get("session")
    support_data = database.fetch_to_dict("SELECT * FROM supports WHERE id = %s", (id,))
    if not support_data: return "Invalid supporter ID"
    if support_data["user"] is not None: return "Supporter has already been claimed"

    if not session_id:
        return redirect(f"/account/login?supporter_id={id}")
    else:
        user_id = Account.id_from_session(session_id)
        Account.claim_supporter(id, user_id)
        return redirect(f"/account/{user_id}")


@main_blueprint.route("/status")
def status(): return render_template("status.html")


# endregion


# region Fillers
@main_blueprint.route("/user/<id>")
def user_redirect(id): return redirect(f"/account/{id}")
# endregion
