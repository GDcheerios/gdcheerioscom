from flask import Blueprint, render_template

import environment
from api.osu_api import get_matches

osu_blueprint = Blueprint('osu_blueprint', __name__)


@osu_blueprint.route("/")
def osu():
    return render_template("osu/index.html", matches=get_matches)


@osu_blueprint.route("/match/<id>")
def osu_match(id):
    match = environment.database.fetch_to_dict("SELECT * FROM osu_matches WHERE id = %s", params=(id,))
    return render_template('osu/match.html')
