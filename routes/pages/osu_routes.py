from flask import Blueprint, render_template, request

import environment
from api.osu_api import get_matches, fetch_osu_data, get_recent_scores
from objects.Account import Account

osu_blueprint = Blueprint('osu_blueprint', __name__)


@osu_blueprint.route("/")
def osu():
    request_id = Account.id_from_session(request.cookies.get('session'))
    account = None
    if request_id:
        account = Account(request_id)

    return render_template("osu/index.html", matches=get_matches(), account=account)


@osu_blueprint.route("/match/<int:id>")
def osu_match(id):
    match = environment.database.fetch_to_dict(
        "SELECT * FROM osu.matches WHERE id = %s",
        params=(id,)
    )
    player_ids = [player_id[0] for player_id in environment.database.fetch_all(
        "SELECT user_id FROM osu.match_users WHERE match_id = %s AND placement <= 20 ORDER BY placement LIMIT 20", params=(id,))]
    recent_scores = get_recent_scores(id)

    if not match:
        return "Match not found", 404

    current_osu_id = None
    request_id = Account.id_from_session(request.cookies.get("session"))
    is_creator = str(request_id) == str(match["opener_id"])
    is_admin = False
    if request_id:
        account = Account(request_id)
        is_admin = bool(account.is_admin)
        osu_data = account.get_osu_data()
        if osu_data:
            current_osu_id = osu_data["id"]

    in_match = False
    if current_osu_id:
        result = environment.database.fetch_one("SELECT 1 FROM osu.match_users WHERE match_id = %s AND user_id = %s",
                                                params=(id, current_osu_id))
        in_match = True if result else False

    if in_match and current_osu_id not in player_ids:
        player_ids.append(current_osu_id)

    return render_template(
        'osu/match.html',
        match=match,
        current_osu_id=current_osu_id,
        is_creator=is_creator,
        is_admin=is_admin,
        match_id=id,
        id=request_id,
        in_match=in_match,
        websocket_url=environment.frontend_websocket_url,
        player_ids=player_ids,
        recent_scores=recent_scores
    )
