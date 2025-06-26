from flask import Blueprint, render_template, redirect

import environment
from api.gentrys_quest.leaderboard_api import *

main_blueprint = Blueprint("main_blueprint", __name__)


@main_blueprint.route("/")
def index(): return render_template(
    "index.html",
    rankings=leaderboard(amount=5),
    weekly_event=in_game_leaderboard(3, 5, commas=True)
)


@main_blueprint.route("/about")
def about(): return render_template(
    "about.html",
    osu_user=environment.database.fetch_to_dict("SELECT * FROM osu_users WHERE id = 11339405;")
)


@main_blueprint.route("/user/<id>")
def user_redirect(id): return redirect(f"/account/{id}")
