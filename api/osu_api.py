import requests
import datetime as dt

import environment

expiration = 0
token = 0


def client_grant():
    global expiration
    global token
    print("granting client...")
    response = requests.post(f"https://osu.ppy.sh/oauth/token",
                             headers={"Accept": "application/json", "Content-Type": "application/json"},
                             json={"client_id": environment.osu_client_id, "client_secret": f"{environment.osu_secret}",
                                   "grant_type": "client_credentials", "scope": "public"}).json()
    dt_obj = dt.datetime.now()
    expiration = round(dt_obj.microsecond / 1000) + response["expires_in"]
    token = response["access_token"]
    return token


def check_access():
    global expiration
    global token
    print("checking access...")
    dt_obj = dt.datetime.now()

    try:
        if round(dt_obj.microsecond / 1000) > expiration:
            print("renewing token")
            token = client_grant()

    except Exception as E:
        print(E)
        token = client_grant()

    return token


def get_user_info(id: int):
    print(f"getting osu user {id}")
    return requests.get(f"https://osu.ppy.sh/api/v2/users/{id}/osu", headers={
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {check_access()}"
    }).json()
