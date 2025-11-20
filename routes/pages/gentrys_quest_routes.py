from flask import Blueprint, render_template, redirect

import environment
from api.gentrys_quest.leaderboard_api import get_top_players, get_leaderboard

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


@gentrys_quest_blueprint.route("/levels")
def gentrys_quest_levels(): return render_template(
    "gentrys quest/levels.html",
    levels=environment.gq_levels,
    level_colors=environment.gq_level_colors
)


@gentrys_quest_blueprint.route("/merch")
def gentrys_quest_merch(): return redirect("https://gentrysquestshop.printify.me/")
