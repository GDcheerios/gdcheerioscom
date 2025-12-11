import json
import urllib
import requests
from flask import Blueprint, request, redirect

import environment
from api import osu_api

osu_api_blueprint = Blueprint('osu_api_blueprint', __name__)


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
    data = osu_api.extract_info(osu_api.get_user_info(id))
    if data:
        ids = environment.database.fetch_all("select match from osu_match_users where id = %s", params=(id,))

        # for id in ids:
        # TODO: use sockets to update on frontend for other users

    return data


@osu_api_blueprint.route('/osu/create-match', methods=['POST'])
def create_match():
    global team_name
    team_name = None
    data = request.json
    print(data)
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
