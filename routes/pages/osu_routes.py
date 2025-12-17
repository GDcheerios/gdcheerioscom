from flask import Blueprint, render_template, request

import environment
from api.osu_api import get_matches
from objects import Account

osu_blueprint = Blueprint('osu_blueprint', __name__)


@osu_blueprint.route("/")
def osu():
    request_id = request.cookies.get("userID")
    account = None
    if request_id:
        account = Account(request_id)

    return render_template("osu/index.html", matches=get_matches(), account=account)


@osu_blueprint.route("/match/<id>")
def osu_match(id):
    match = environment.database.fetch_to_dict("SELECT * FROM osu_matches WHERE id = %s", params=(id,))
    players = environment.database.fetch_all_to_dict(
        "SELECT omu.*, ou.* FROM public.osu_match_users omu "
        "LEFT JOIN public.osu_users ou ON omu.user = ou.id "
        "WHERE omu.match = %s",
        params=(id,)
    )
    current_osu_id = None
    request_id = request.cookies.get("userID")
    is_creator = request_id == str(match["opener"])
    if request_id:
        current_osu_id = Account(request_id).osu_id

    return render_template('osu/match.html', match=match, players=players, current_osu_id=current_osu_id, is_creator=is_creator)


@osu_blueprint.route("/loading/<reason>/<id>")
def osu_loading(reason, id): return render_template("osu/loading.html", reason=reason, id=id, msg="")