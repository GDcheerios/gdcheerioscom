import requests
from flask import Blueprint, render_template, redirect, request

import environment
from api.gentrys_quest.leaderboard_api import *
from api.account_api import Account

main_blueprint = Blueprint("main_blueprint", __name__)


# region Routes
@main_blueprint.route("/")
def index():
    try:
        latest = environment.storage.get_latest_changelog(
            project="gdcheerioscom",
            output_format="html",
        )
    except requests.RequestException:
        latest = None
    return render_template("index.html", changelog=latest)


@main_blueprint.route("/about")
def about(): return render_template("about.html")


@main_blueprint.route("/changelog")
def changelog():
    try:
        projects = environment.storage.get_changelogs(output_format="html")
    except requests.RequestException:
        return render_template("changelog.html", projects=[], unavailable=True), 503
    return render_template("changelog.html", projects=projects, unavailable=False)


@main_blueprint.route("/search")
def search(): return render_template("search.html")


@main_blueprint.get("/search/results")
def search_results():
    query = request.args.get("q", "")
    if not query:
        return redirect("/search")

    users_result = Account.search(query)
    osu_result = environment.database.fetch_all_to_dict("select * from osu.matches where name ilike %s limit 5",
                                                        params=(f"%{query}%",))
    return {
        "users": users_result,
        "matches": osu_result
    }


@main_blueprint.route("/supporter")
def supporter(): return render_template("supporter.html", logged_in=request.cookies.get("session") is not None)


@main_blueprint.route("/supporter/claim/<id>")
def supporter_claim(id):
    session_id = request.cookies.get("session")
    support_data = database.fetch_to_dict("SELECT * FROM account.supports WHERE id = %s", (id,))
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
