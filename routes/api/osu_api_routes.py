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
    if match_id is not None:
        try:
            match_id = int(match_id)
        except (TypeError, ValueError):
            match_id = None

    skip_api = request.args.get("skip_api", "false").lower() == "true"
    data = osu_api.fetch_osu_data(id, skip_api=skip_api)

    if not data:
        return {"error": "user not found"}

    return _json_safe(data)


@osu_api_blueprint.post('/osu/add-user')
def fetch_osu_user_matches():
    user = request.json["user"]
    match_id = request.json["match"]

    user = osu_api.fetch_osu_data(user)

    environment.database.execute(
        """
        INSERT INTO osu.match_users 
            (match_id, user_id, starting_score, starting_playcount)
        values 
            (%s, %s, %s, %s)
        """,
        params=(match_id, user['id'], user['total_score'], user['playcount'])
    )
    return {"success": True}


@osu_api_blueprint.post('/osu/remove-user')
def remove_osu_user_from_match():
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
        INSERT INTO osu.matches
        (name,
         opener_id,
         open)
        values (%s,
                %s,
                %s)
        returning id
        """,
        params=(data["matchName"], user_id, data["open"])
    )[0]
    for player in data["players"]:
        in_team = False
        for team in data["teams"]:
            if player in team["players"]:
                team_name = team["name"]
                in_team = True

            if not in_team:
                team_name = None

        player_data = osu_api.fetch_osu_data(player)
        print(player_data)
        logger.info("create_match match_id=%s", match_id)
        environment.database.execute(
            "INSERT INTO osu.match_users (match_id, user_id, starting_score, starting_playcount, team) values (%s, %s, %s, %s, %s)",
            params=(match_id, player_data["id"], player_data["total_score"], player_data["playcount"], team_name))

    return {
        "id": match_id
    }


@osu_api_blueprint.post('/osu/refresh-match_id/<id>')
def refresh_all_in_match(id: int):
    users = environment.database.fetch_all("SELECT user_id FROM osu.match_users WHERE match_id = %s", params=(id,))
    for user in users:
        data = osu_api.fetch_osu_data(user[0])
        if data:
            _notify_osu_user_refreshed(data, match_id=id)

    return {"success": True}


@osu_api_blueprint.post('/osu/end-match/<id>')
def end_match(id):
    match_id = environment.database.fetch_to_dict("SELECT * FROM osu.matches WHERE id = %s", params=(id,))
    if str(Account.id_from_session(request.cookies.get("session"))) != str(match_id["opener_id"]):
        return {"error": "not your match_id"}

    match_users = environment.database.fetch_all("SELECT user_id FROM osu.match_users WHERE match_id = %s", params=(id,))
    logger.info("ending match id=%s users=%s", id, match_users)
    environment.database.execute("UPDATE osu.matches SET ended = true WHERE id = %s", params=(id,))
    for user in match_users:
        user = user[0]
        user = osu_api.fetch_osu_data(user)
        environment.database.execute(
            """
            UPDATE osu.match_users
            SET ending_score     = %s,
                ending_playcount = %s
            WHERE user_id = %s
              AND match_id = %s;
            """,
            params=(user["total_score"], user["playcount"], user["id"], id)
        )

    return {"success": True}
# endregion
