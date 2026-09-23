import json
import re
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


@osu_api_blueprint.get('/osu/get-team/<id>')
def fetch_osu_team(id):
    return _json_safe(osu_api.get_team(id))


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
        ORDER BY placement
        """,
        params=(match_id, f"%{query}%")
    )]

    print(user_ids)

    return user_ids


@osu_api_blueprint.get('/osu/team-users/<int:id>')
def fetch_osu_team_users(id): return osu_api.get_team_users(id)


@osu_api_blueprint.post('/osu/add-user')
def add_osu_user():
    user = request.json["user"]
    match_id = request.json["match_id"]

    user = osu_api.fetch_osu_data(user)['user']

    existing = environment.database.fetch_one(
        """
        SELECT user_id
        FROM osu.match_users
        WHERE match_id = %s
          AND user_id = %s
        """,
        params=(match_id, user['id'])
    )

    if existing:
        return {"error": "user already in match"}

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


@osu_api_blueprint.post('/osu/change-team')
def change_team():
    account_id = Account.id_from_session(request.cookies.get("session"))
    if not account_id:
        return {"error": "Sign in to change teams."}, 401

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return {"error": "Expected match_id, user and team_id."}, 400

    for key in ("match_id", "user", "team_id"):
        value = data.get(key)
        if key == "team_id" and key in data and value is None:
            continue
        if type(value) is not int or value <= 0:
            return {"error": "Invalid " + key + "."}, 400

    match_id, user_id, team_id = data["match_id"], data["user"], data["team_id"]
    match = environment.database.fetch_to_dict(
        "SELECT opener_id, ended FROM osu.matches WHERE id = %s", params=(match_id,))

    if not match:
        return {"error": "Match not found."}, 404
    if str(match["opener_id"]) != str(account_id) and not Account(account_id).is_admin:
        return {"error": "Only the match creator or an admin can change teams."}, 403
    if match["ended"]:
        return {"error": "This match has ended."}, 409

    if team_id is not None and not environment.database.fetch_one(
            "SELECT id FROM osu.teams WHERE id = %s AND match_id = %s",
            params=(team_id, match_id)):
        return {"error": "Team not found in this match."}, 400

    updated = environment.database.fetch_one(
        "UPDATE osu.match_users SET team_id = %s WHERE match_id = %s AND user_id = %s RETURNING user_id",
        params=(team_id, match_id, user_id))

    if not updated:
        return {"error": "Player not found in this match."}, 404

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


@osu_api_blueprint.post('/osu/freeze')
def freeze_user():
    user_id = request.json["userId"]
    match_id = request.json["match"]
    user = osu_api.fetch_osu_data(user_id, skip_api=True)["user"]
    environment.database.execute(
        """
        UPDATE osu.match_users
        SET ending_stats = %s
        WHERE user_id = %s
          AND match_id = %s;
        """,
        params=(json.dumps(_json_safe(user)), user_id, match_id)
    )
    return {"success": True}


# endregion


# region match_id API

def _validate_team(team):
    if not isinstance(team, dict):
        raise ValueError("Each team must be an object.")
    name, acronym, color = (team.get(key) for key in ("name", "acronym", "color"))
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Enter a team name.")
    if not isinstance(acronym, str) or not 1 <= len(acronym.strip().upper()) <= 4:
        raise ValueError("Team acronyms must contain 1–4 characters.")
    if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise ValueError("Team colors must use #RRGGBB format.")
    return {"name": name.strip(), "acronym": acronym.strip().upper(), "color": color.lower()}


@osu_api_blueprint.post('/osu/create-team')
def create_team():
    user_id = Account.id_from_session(request.cookies.get("session"))

    if not user_id:
        return {"error": "Sign in to create a team."}, 401

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return {"error": "Expected a team object and match_id."}, 400

    try:
        team = _validate_team(data.get("team"))
        match_id = int(data.get("match_id"))
    except (ValueError, TypeError) as exc:
        return {"error": str(exc) if isinstance(exc, ValueError) else "Invalid match ID."}, 400

    match = environment.database.fetch_to_dict(
        "SELECT opener_id, ended FROM osu.matches WHERE id = %s", params=(match_id,))

    if not match:
        return {"error": "Match not found."}, 404

    if str(match["opener_id"]) != str(user_id):
        return {"error": "Only the match creator can add teams."}, 403

    if match["ended"]:
        return {"error": "This match has ended."}, 409

    team = environment.database.fetch_to_dict(
        """
        INSERT INTO osu.teams (name, acronym, color, match_id) VALUES (%s, %s, %s, %s) RETURNING *
        """, params=(team["name"], team["acronym"], team["color"], match_id)
    )
    if not team:
        return {"error": "Could not save team. Please try again."}, 500
    return {"team": _json_safe(team)}, 201


@osu_api_blueprint.post('/osu/create-match')
def create_match():
    data = request.json

    # configuration
    match_name = data["matchName"]
    objective = data["objective"]
    open = data["open"]

    teams = data["teams"]
    players = data["players"]

    user_id = Account.id_from_session(request.cookies.get("session"))
    match_id = environment.database.fetch_one(
        """
        INSERT INTO osu.matches(name,
                                opener_id,
                                open,
                                objective)
        VALUES (%s,
                %s,
                %s,
                %s)
        RETURNING id
        """,
        params=(match_name, user_id, open, objective)
    )[0]

    logger.info("create_match match_id=%s", match_id)

    for local_team_id, team in teams.items():
        team["localID"] = local_team_id

        db_result = environment.database.fetch_one(
            "INSERT INTO osu.teams (match_id, name, acronym, color) VALUES (%s, %s, %s, %s) RETURNING id",
            params=(match_id, team["name"], team["acronym"], team["color"])
        )
        team["dbID"] = db_result[0]

    for player_id, player_data in players.items():
        osu_player = osu_api.fetch_osu_data(player_id, skip_api=True)
        user_stats = osu_player["user"]
        user_stats["reconstructed_pp"] = 0
        safe_stats_json = json.dumps(_json_safe(user_stats))

        team_db_id = None
        if len(teams.items()) != 0:
            local_team_id = player_data["team"]
            team_db_id = teams[local_team_id]["dbID"]

        environment.database.execute(
            "INSERT INTO osu.match_users (match_id, user_id, starting_stats, team_id) VALUES (%s, %s, %s::jsonb, %s)",
            params=(match_id, player_id, safe_stats_json, team_db_id)
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


@osu_api_blueprint.get('/osu/get-metrics/<int:match_id>')
def get_metrics(match_id):
    return environment.database.fetch_all_to_dict(
        """
        SELECT * FROM osu.match_metrics WHERE match_id = %s and placement <= 10
        ORDER BY date ASC, placement ASC
        """,
        params=(match_id,)
    )


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
