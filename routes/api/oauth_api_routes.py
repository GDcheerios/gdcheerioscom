import json
import urllib

import requests
from flask import Blueprint, request, redirect

import environment
from api.osu_api import fetch_osu_data

oauth_api_routes = Blueprint('oauth', __name__)


@oauth_api_routes.route('/osu')
def osu_callback():
    code = urllib.parse.parse_qs(request.query_string.decode('utf-8'))["code"][0]

    response = requests.post("https://osu.ppy.sh/oauth/token",
                             json={'client_id': environment.osu_client_id,
                                   'code': code,
                                   'client_secret': environment.osu_secret,
                                   'grant_type': 'authorization_code',
                                   'redirect_uri': f"{environment.domain}/oauth/osu",
                                   'scope': 'public'},
                             headers={'Accept': 'application/json',
                                      'Content-Type': 'application/json'})

    response = response.json()
    print(response)

    user_info = requests.get("https://osu.ppy.sh/api/v2/me/osu", headers={
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': f"Bearer {response['access_token']}"
    }).json()

    print(user_info)

    info = fetch_osu_data(user_info["id"])

    return redirect(f"/account/create?osu_info={json.dumps(info)}")
