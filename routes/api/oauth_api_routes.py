import json
import urllib

import requests
from flask import Blueprint, request, redirect, session

import environment
from api.osu_api import fetch_osu_data

oauth_api_routes = Blueprint('oauth', __name__)


@oauth_api_routes.route('/google/login')
def google_login():
    """
    Login with google to then redirect to the oauth.
    """
    state = "randomval"

    params = {
        "client_id": environment.google_client_id,
        "redirect_uri": f"{environment.domain}/oauth/google",
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }

    return redirect("https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params))


@oauth_api_routes.route('/google')
def google_callback():
    """
    Google oauth which pushes values back to account creation
    """
    qs = urllib.parse.parse_qs(request.query_string.decode('utf-8'))

    if "error" in qs:
        return redirect("/account/create?msg=" + urllib.parse.quote(qs["error"][0]))

    if "code" not in qs:
        return redirect("/account/create?msg=" + urllib.parse.quote("Missing OAuth code"))

    returned_state = qs.get("state", [None])[0]
    expected_state = session.get("google_oauth_state")
    if expected_state and returned_state != expected_state:
        return redirect("/account/create?msg=" + urllib.parse.quote("Invalid OAuth state"))

    code = qs["code"][0]

    token_res = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": environment.google_client_id,
            "client_secret": environment.google_client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": f"{environment.domain}/oauth/google",
        },
        headers={"Accept": "application/json"},
        timeout=15,
    )

    if token_res.status_code != 200:
        return redirect("/account/create?msg=" + urllib.parse.quote("Google token exchange failed"))

    tokens = token_res.json()
    access_token = tokens.get("access_token")
    if not access_token:
        return redirect("/account/create?msg=" + urllib.parse.quote("Missing access token from Google"))

    userinfo_res = requests.get(
        "https://openidconnect.googleapis.com/v1/userinfo",
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        timeout=15,
    )

    if userinfo_res.status_code != 200:
        return redirect("/account/create?msg=" + urllib.parse.quote("Failed to fetch Google user info"))

    google_info = userinfo_res.json()

    username_guess = (
        (google_info.get("email", "").split("@")[0] if google_info.get("email") else None)
        or google_info.get("given_name")
        or google_info.get("name")
        or ""
    )

    return redirect(
        "/account/create"
        + f"?google_info={urllib.parse.quote(json.dumps(google_info))}"
        + f"&username={urllib.parse.quote(username_guess)}"
        + f"&email={google_info.get("email", "")}"
        + "&msg=Please fill out required information"
    )


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

    user_info = requests.get("https://osu.ppy.sh/api/v2/me/osu", headers={
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': f"Bearer {response['access_token']}"
    }).json()

    info = fetch_osu_data(user_info["id"])

    return redirect(
            f"/account/create" +
            f"?osu_info={json.dumps(info)}" +
            f"&username={info['username']}" +
            "&msg=Please fill out required information"
    )
