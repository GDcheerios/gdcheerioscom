from flask import Blueprint, render_template, redirect, request

import environment
from api.gentrys_quest.leaderboard_api import get_top_players, get_leaderboard
from objects import Account

gentrys_quest_blueprint = Blueprint("gentrys_quest_blueprint", __name__)


# inject variables into templates
@gentrys_quest_blueprint.context_processor
def inject_version(): return {
    "gq_version": environment.gq_version,
    "rater": environment.gq_rater,
    "get_top_players": get_top_players,
    "get_leaderboard": get_leaderboard
}


@gentrys_quest_blueprint.route("/")
def gentrys_quest_home(): return render_template("gentrys quest/home.html")


@gentrys_quest_blueprint.route("/leaderboard")
def gentrys_quest_leaderboard(): return render_template("gentrys quest/leaderboard.html")


@gentrys_quest_blueprint.route("/levels")
def gentrys_quest_levels(): return render_template(
    "gentrys quest/levels.html",
    levels=environment.gq_levels,
    level_colors=environment.gq_level_colors
)


@gentrys_quest_blueprint.route("/ranking")
def gentrys_quest_ranking():
    global user_ranking
    user_id = request.cookies.get("userID")
    if user_id:
        user_ranking = Account(user_id).gq_data["ranking"]
    return render_template("gentrys quest/ranking.html", user_ranking=user_ranking)
