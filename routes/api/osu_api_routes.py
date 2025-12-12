import json
import urllib
import requests
from flask import Blueprint, request, redirect

from decimal import Decimal
from datetime import date, datetime

import environment
from api import osu_api

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
def osu_user(id):
    data = osu_api.fetch_osu_data(id)

    if not data:
        return {"error": "user not found"}

    match_rows = environment.database.fetch_all(
        "select match from osu_match_users where \"user\" = %s",
        params=(data["id"],)
    )

    safe_player = _json_safe(data)

    print(f"emitting {safe_player} to\n{match_rows}")
    for (match_id,) in match_rows:
        match_id = str(match_id)
        environment.socket.emit(
            "match_user_score_updated",
            {
                "match_id": match_id,
                "player": safe_player,
            },
            room=f"match:{match_id}"
        )

    return data


@osu_api_blueprint.route('/osu/create-match', methods=['POST'])
def create_match():
    global team_name
    team_name = None
    data = request.json
    match_id = environment.database.fetch_one("INSERT INTO osu_matches (name) values (%s) returning id",
                                                  params=(data["matchName"],))[0]
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
