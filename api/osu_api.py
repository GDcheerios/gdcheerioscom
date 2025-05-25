import requests
import datetime as dt

import environment

expiration = 0


def client_grant():
    global expiration
    print("granting client...")
    response = requests.post(f"https://osu.ppy.sh/oauth/token",
                             headers={"Accept": "application/json", "Content-Type": "application/json"},
                             json={"client_id": environment.osu_client_id, "client_secret": f"{environment.osu_secret}",
                                   "grant_type": "client_credentials", "scope": "public"}).json()
    dt_obj = dt.datetime.now()
    expiration = round(dt_obj.microsecond / 1000) + response["expires_in"]
    return response["access_token"]


def check_access():
    dt_obj = dt.datetime.now()
    response = None

    try:
        if round(dt_obj.microsecond / 1000) > expiration:
            print("renewing token")
            response = client_grant()

    except Exception as E:
        print(E)
        response = client_grant()

    return response


def get_user_info(id: int):
    print("getting osu user...")
    return requests.get(f"https://osu.ppy.sh/api/v2/users/{id}/osu", headers={
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {check_access()}"
    }).json()
