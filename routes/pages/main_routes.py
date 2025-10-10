from flask import Blueprint, render_template, redirect

import environment
from api.gentrys_quest.leaderboard_api import *

main_blueprint = Blueprint("main_blueprint", __name__)


@main_blueprint.route("/")
def index(): return render_template("index.html")


@main_blueprint.route("/about")
def about(): return render_template("about.html")


@main_blueprint.route("/user/<id>")
def user_redirect(id): return redirect(f"/account/{id}")
