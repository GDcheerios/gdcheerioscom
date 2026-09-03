import json
import urllib
import requests
from flask import Blueprint, request, redirect

from decimal import Decimal
from datetime import date, datetime

import environment
from api import osu_api
from objects.Account import Account
from utils.logger import setup_logger

osu_api_blueprint = Blueprint('osu_api_blueprint', __name__)
logger = setup_logger("routes.api.osu")


def _json_safe(value):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


# region User API

@osu_api_blueprint.get('/osu/fetch-user/<id>')
def fetch_osu_user(id):
    match_id = request.args.get("match")
    skip_api = request.args.get("skip_api", "false").lower() == "true"
    data = osu_api.fetch_osu_data(id, skip_api=skip_api, match_id=match_id)

    if not data:
        return {"error": "user not found"}

    return _json_safe(data)


@osu_api_blueprint.get('/osu/search/<query>')
def search_osu_user(query):
    match_id = request.args.get("match_id")
    print(match_id, query)
    user_ids = [id[0] for id in environment.database.fetch_all(
        """
        SELECT m.user_id
        FROM osu.match_users m
                 JOIN osu.users u ON m.user_id = u.id
        WHERE m.match_id = %s
          and username ILIKE %s
        """,
        params=(match_id, f"%{query}%")
    )]

    print(user_ids)

    return user_ids


@osu_api_blueprint.post('/osu/add-user')
def add_osu_user():
    user = request.json["user"]
    match_id = request.json["match_id"]

    user = osu_api.fetch_osu_data(user)['user']

    environment.database.execute(
        """
        INSERT INTO osu.match_users
            (match_id, user_id, starting_stats)
        values (%s, %s, %s)
        """,
        params=(match_id, user['id'], json.dumps(_json_safe(user)))
    )
    return _json_safe(user)


@osu_api_blueprint.post('/osu/remove-user')
def remove_osu_user():
    user = request.json["user"]
    match_id = request.json["match"]

    environment.database.execute(
        """
        DELETE
        FROM osu.match_users
        WHERE match_id = %s
          AND user_id = %s
        """,
        params=(match_id, user)
    )
    return {"success": True}


@osu_api_blueprint.post('/osu/change-nickname')
def change_nickname():
    user = request.json["user"]
    match_id = request.json["match"]
    nickname = request.json["nickname"]
    if nickname == "":
        nickname = None

    environment.database.execute(
        """
        UPDATE osu.match_users
        SET nickname = %s
        WHERE match_id = %s
          AND user_id = %s
        """,
        params=(nickname, match_id, user)
    )
    return {"success": True}


# endregion


# region match_id API

@osu_api_blueprint.post('/osu/create-match')
def create_match():
    global team_name
    team_name = None
    data = request.json
    user_id = Account.id_from_session(request.cookies.get("session"))
    match_id = environment.database.fetch_one(
        """
        INSERT INTO osu.matches(name,
                                opener_id,
                                open,
                                primary_objective,
                                secondary_objective)
        VALUES (%s,
                %s,
                %s,
                %s,
                %s)
        RETURNING id
        """,
        params=(data["matchName"], user_id, data["open"], data["primaryObjective"], data["secondaryObjective"])
    )[0]
    logger.info("create_match match_id=%s", match_id)
    for id in data["players"]:
        player = osu_api.fetch_osu_data(id, skip_api=True)
        player["user"]["reconstructed_pp"] = 0
        environment.database.execute(
            "INSERT INTO osu.match_users (match_id, user_id, starting_stats, team) values (%s, %s, %s::jsonb, %s)",
            params=(match_id, id, json.dumps(_json_safe(player["user"])), data["players"][id]["team"])
        )

    return {
        "id": match_id,
        "data": data
    }


@osu_api_blueprint.post('/osu/end-match/<id>')
def end_match(id):
    match = environment.database.fetch_to_dict("SELECT * FROM osu.matches WHERE id = %s", params=(id,))
    if str(Account.id_from_session(request.cookies.get("session"))) != str(match["opener_id"]):
        return {"error": "not your match_id"}

    match_users = [user[0] for user in
                   environment.database.fetch_all("SELECT user_id FROM osu.match_users WHERE match_id = %s",
                                                  params=(id,))]
    logger.info("ending match id=%s users=%s", id, match_users)
    environment.database.execute("UPDATE osu.matches SET ended = true WHERE id = %s", params=(id,))
    for user in match_users:
        user = osu_api.fetch_osu_data(user, skip_api=True)["user"]
        environment.database.execute(
            """
            UPDATE osu.match_users
            SET ending_stats = %s
            WHERE user_id = %s
              AND match_id = %s;
            """,
            params=(json.dumps(_json_safe(user)), user["id"], id)
        )

    return {"success": True}


# endregion

# region scores

@osu_api_blueprint.get('/osu/score/<int:id>')
def get_score(id):
    return environment.database.fetch_to_dict("SELECT * FROM osu.scores WHERE id = %s", params=(id,))


@osu_api_blueprint.get('/osu/scores/<int:match_id>/recent')
def get_recent_scores(match_id: int):
    limit = request.args.get("limit", type=int, default=5)

    return osu_api.get_recent_scores(match_id, limit)


@osu_api_blueprint.get('/osu/scores/<int:match_id>/best')
def get_best_score(match_id):
    limit = request.args.get("limit", type=int, default=5)

    return osu_api.get_best_scores(match_id, limit)

# endregion
