from flask import Blueprint, render_template, request

import environment
from api.osu_api import get_matches
from objects import Account

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
    match = environment.database.fetch_to_dict("SELECT * FROM osu_matches WHERE id = %s", params=(id,))
    players = environment.database.fetch_all_to_dict(
        """
        SELECT
            omu.match,
            omu."user",
            omu.starting_score,
            omu.starting_playcount,
            omu.ending_score,
            omu.ending_playcount,
            omu.team,
            omu.nickname,
            ou.id         AS id,
            ou.username   AS username,
            ou.score      AS score,
            ou.playcount  AS playcount,
            ou.accuracy   AS accuracy,
            ou.performance AS performance,
            ou.rank       AS rank,
            ou.avatar     AS avatar,
            ou.background AS background,
            ou.last_refresh AS last_refresh
        FROM public.osu_match_users omu
        LEFT JOIN public.osu_users ou ON omu."user" = ou.id
        WHERE omu.match = %s
        """,
        params=(id,)
    )
    current_osu_id = None
    request_id = Account.id_from_session(request.cookies.get('session'))
    is_creator = str(request_id) == str(match["opener"])
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
        players=players,
        current_osu_id=current_osu_id,
        is_creator=is_creator,
        is_admin=is_admin,
        websocket_url=environment.websocket_url,
    )


@osu_blueprint.route("/loading/<reason>/<id>")
def osu_loading(reason, id): return render_template("osu/loading.html", reason=reason, id=id, msg="")
