from flask import Blueprint, render_template, request

import environment
from api.osu_api import get_matches
from objects.Account import Account

osu_blueprint = Blueprint('osu_blueprint', __name__)


@osu_blueprint.route("/")
def osu():
    request_id = Account.id_from_session(request.cookies.get('session'))
    account = None
    if request_id:
        account = Account(request_id)

    return render_template("osu/index.html", matches=get_matches(), account=account)


@osu_blueprint.route("/match/<id>")
def osu_match(id):
    match = environment.database.fetch_to_dict("SELECT * FROM osu.matches WHERE id = %s", params=(id,))
    current_osu_id = None
    request_id = Account.id_from_session(request.cookies.get('session'))
    is_creator = str(request_id) == str(match["opener_id"])
    is_admin = False
    if request_id:
        account = Account(request_id)
        is_admin = bool(account.is_admin)
        osu_data = account.get_osu_data()
        if osu_data:
            current_osu_id = osu_data["id"]

    return render_template(
        'osu/match.html',
        match=match,
        current_osu_id=current_osu_id,
        is_creator=is_creator,
        is_admin=is_admin,
        match_id=id,
        websocket_url=environment.frontend_websocket_url,
    )
