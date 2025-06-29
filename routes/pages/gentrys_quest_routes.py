from flask import Blueprint, render_template, redirect

import environment

gentrys_quest_blueprint = Blueprint("gentrys_quest_blueprint", __name__)


@gentrys_quest_blueprint.route("/")
def gentrys_quest_home(): return render_template("gentrys quest/home.html")


@gentrys_quest_blueprint.route("/levels")
def gentrys_quest_levels(): return render_template("gentrys quest/levels.html", levels=environment.gq_levels)


@gentrys_quest_blueprint.route("/merch")
def gentrys_quest_merch(): return redirect("https://gentrysquestshop.printify.me/")
