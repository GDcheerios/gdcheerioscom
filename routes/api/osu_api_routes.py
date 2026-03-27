import json
import urllib
import requests
from flask import Blueprint, request, redirect

from decimal import Decimal
from datetime import date, datetime

import environment
from api import osu_api
from objects import Account
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


def _notify_osu_user_refreshed(user_data, match_id=None):
    websocket_url = getattr(environment, "websocket_url", None)
    if not websocket_url:
        logger.debug("websocket_url is not configured; skipping refresh notification")
        return

    try:
        from websockets.sync.client import connect
    except Exception:
        logger.exception("websockets client library is not available")
        return

    match_ids = []
    try:
        if match_id is not None:
            match_ids = [int(match_id)]
        elif user_data and user_data.get("id") is not None:
            rows = environment.database.fetch_all(
                """
                SELECT DISTINCT match
                FROM osu_match_users
                WHERE "user" = %s
                """,
                params=(user_data["id"],)
            )
            match_ids = [int(row[0]) for row in rows]
    except Exception:
        logger.exception("failed to compute match_ids for refreshed osu user")

    payload = {
        "type": "osu_user_refreshed",
        "match_id": int(match_id) if match_id is not None else None,
        "match_ids": match_ids,
        "user": _json_safe(user_data),
    }

    if match_id is not None and user_data and user_data.get("id") is not None:
        try:
            match_user = environment.database.fetch_to_dict(
                """
                SELECT
                    match,
                    "user",
                    starting_score,
                    starting_playcount,
                    ending_score,
                    ending_playcount,
                    team,
                    nickname
                FROM osu_match_users
                WHERE match = %s
                  AND "user" = %s
                """,
                params=(int(match_id), int(user_data["id"]))
            )
            if match_user:
                payload["match_user"] = _json_safe(match_user)
        except Exception:
            logger.exception("failed to include match_user payload for refresh notification")

    try:
        with connect(websocket_url) as ws:
            ws.send(json.dumps(payload))
            response = ws.recv()
            logger.info("osu refresh notification acknowledged: %s", response)
    except Exception:
        logger.exception("failed to send osu refresh notification")


# region User API

@osu_api_blueprint.get('/osu/fetch-user/<id>')
def fetch_osu_user(id):
    match_id = request.args.get("match_id")
    if match_id is not None:
        try:
            match_id = int(match_id)
        except (TypeError, ValueError):
            match_id = None

    data = osu_api.fetch_osu_data(id)

    if not data:
        return {"error": "user not found"}

    _notify_osu_user_refreshed(data, match_id=match_id)
    return _json_safe(data)


@osu_api_blueprint.post('/osu/add-user')
def fetch_osu_user_matches():
    user = request.json["user"]
    match = request.json["match"]

    user = osu_api.fetch_osu_data(user)

    environment.database.execute(
        """
        INSERT INTO osu_match_users 
            (match, "user", starting_score, starting_playcount)
        values 
            (%s, %s, %s, %s)
        """,
        params=(match, user['id'], user['score'], user['playcount'])
    )
    return {"success": True}


@osu_api_blueprint.post('/osu/remove-user')
def remove_osu_user_from_match():
    user = request.json["user"]
    match = request.json["match"]

    environment.database.execute(
        """
        DELETE
        FROM osu_match_users
        WHERE match = %s
          AND "user" = %s
        """,
        params=(match, user)
    )
    return {"success": True}


@osu_api_blueprint.post('/osu/change-nickname')
def change_nickname():
    user = request.json["user"]
    match = request.json["match"]
    nickname = request.json["nickname"]
    if nickname == "":
        nickname = None

    environment.database.execute(
        """
        UPDATE osu_match_users
        SET nickname = %s
        WHERE match = %s
          AND "user" = %s
        """,
        params=(nickname, match, user)
    )
    return {"success": True}


# endregion


# region Match API

@osu_api_blueprint.post('/osu/create-match')
def create_match():
    global team_name
    team_name = None
    data = request.json
    user_id = Account.id_from_session(request.cookies.get("session"))
    match_id = environment.database.fetch_one(
        """
        INSERT INTO osu_matches
        (name,
         opener,
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
        logger.info("create_match match_id=%s", match_id)
        environment.database.execute(
            "INSERT INTO osu_match_users (match, \"user\", starting_score, starting_playcount, team) values (%s, %s, %s, %s, %s)",
            params=(match_id, player_data["id"], player_data["score"], player_data["playcount"], team_name))

    return {
        "id": match_id
    }


@osu_api_blueprint.post('/osu/refresh-match/<id>')
def refresh_all_in_match(id: int):
    users = environment.database.fetch_all("SELECT \"user\" FROM osu_match_users WHERE match = %s", params=(id,))
    for user in users:
        data = osu_api.fetch_osu_data(user[0])
        if data:
            _notify_osu_user_refreshed(data, match_id=id)

    return {"success": True}


@osu_api_blueprint.post('/osu/end-match/<id>')
def end_match(id):
    match = environment.database.fetch_to_dict("SELECT * FROM osu_matches WHERE id = %s", params=(id,))
    if str(Account.id_from_session(request.cookies.get("session"))) != str(match["opener"]):
        return {"error": "not your match"}

    match_users = environment.database.fetch_all("SELECT \"user\" FROM osu_match_users WHERE match = %s", params=(id,))
    logger.info("ending match id=%s users=%s", id, match_users)
    environment.database.execute("UPDATE osu_matches SET ended = true WHERE id = %s", params=(id,))
    for user in match_users:
        user = user[0]
        user = osu_api.fetch_osu_data(user)
        environment.database.execute(
            """
            UPDATE osu_match_users
            SET ending_score     = %s,
                ending_playcount = %s
            WHERE \"user\" = %s
              AND match = %s;
            """,
            params=(user["score"], user["playcount"], user["id"], id)
        )

    return {"success": True}
# endregion
