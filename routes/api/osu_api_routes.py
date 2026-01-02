import json
import urllib
import requests
from flask import Blueprint, request, redirect

from decimal import Decimal
from datetime import date, datetime

import environment
from api import osu_api
from objects import Account

osu_api_blueprint = Blueprint('osu_api_blueprint', __name__)


def _json_safe(value):
    if isinstance(value, Decimal):
        # choose one:
        # return float(value)   # if you want numeric
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


@osu_api_blueprint.route('/code_grab')
def code_grab():
    code = urllib.parse.parse_qs(request.query_string.decode('utf-8'))["code"][0]

    response = requests.post("https://osu.ppy.sh/oauth/token",
                             json={'client_id': environment.osu_client_id,
                                   'code': code,
                                   'client_secret': environment.osu_secret,
                                   'grant_type': 'authorization_code',
                                   'redirect_uri': f"{environment.domain}/api/code_grab",
                                   'scope': 'public'},
                             headers={'Accept': 'application/json',
                                      'Content-Type': 'application/json'})

    response = response.json()

    user_info = requests.get("https://osu.ppy.sh/api/v2/me/osu", headers={
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': f"Bearer {response['access_token']}"
    }).json()

    info = {
        "username": user_info["username"],
        "id": user_info["id"],
        "avatar": f"https://a.ppy.sh/{user_info['id']}",
        "background url": user_info["cover_url"]
    }

    return redirect(f"/account/create?osu_info={json.dumps(info)}")


@osu_api_blueprint.get('/osu/fetch-user/<id>')
def fetch_osu_user(id):
    data = osu_api.fetch_osu_data(id)

    if not data:
        return {"error": "user not found"}

    match_rows = environment.database.fetch_all_to_dict(
        "select * from osu_match_users where \"user\" = %s",
        params=(data["id"],)
    )

    safe_player = _json_safe(data)

    print(f"emitting {safe_player} to\n{len(match_rows)} matches")
    for (match) in match_rows:
        match = _json_safe(match)
        environment.socket.emit(
            "match_user_score_updated",
            {
                "match": match,
                "player": safe_player
            },
            room=f"match:{match["match"]}"
        )

    return data


@osu_api_blueprint.route('/osu/create-match', methods=['POST'])
def create_match():
    global team_name
    team_name = None
    data = request.json
    user_id = Account.id_from_session(request.cookies.get("session"))
    match_id = environment.database.fetch_one(
        """
        INSERT INTO osu_matches
        (name,
         opener)
        values (%s,
                %s)
        returning id
        """,
        params=(data["matchName"], user_id)
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
        print(match_id)
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
        fetch_osu_user(user[0])

    return {"success": True}


@osu_api_blueprint.post('/osu/end-match/<id>')
def end_match(id):
    match = environment.database.fetch_to_dict("SELECT * FROM osu_matches WHERE id = %s", params=(id,))
    if Account.id_from_session(request.cookies.get("session")) != str(match["opener"]):
        return {"error": "not your match"}

    match_users = environment.database.fetch_all("SELECT \"user\" FROM osu_match_users WHERE match = %s", params=(id,))
    print(match_users)
    environment.database.execute("UPDATE osu_matches SET ended = true WHERE id = %s", params=(id,))
    for user in match_users:
        user = user[0]
        user = osu_api.fetch_osu_data(user)
        environment.database.execute(
            """
                UPDATE osu_match_users
                SET
                    ending_score = %s,
                    ending_playcount = %s
                WHERE \"user\" = %s
                  AND match = %s;
            """,
            params=(user["score"], user["playcount"], user["id"], id)
        )

    return {"success": True}
