from flask import Blueprint, render_template

gentrys_quest_blueprint = Blueprint("gentrys_quest_blueprint", __name__)


@gentrys_quest_blueprint.route("/")
async def gentrys_quest_home(): return render_template("gentrys quest/home.html")

