import requests
import datetime as dt
from datetime import timezone

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


def get_user_info(user_identifier):
    """
    Retrieve osu api user info.

    If `user_identifier` can be cast to int, it is treated as a numeric osu ID.
    Otherwise, it is treated as a username.
    """

    try:
        osu_id = int(user_identifier)
        is_id = True
    except (TypeError, ValueError):
        osu_id = None
        is_id = False

    if is_id:
        user_check = environment.database.fetch_to_dict(
            "SELECT * FROM osu_users WHERE id = %s",
            params=(osu_id,)
        )

        if (
                not user_check
                or user_check["last_refresh"]
                <= dt.datetime.now(tz=timezone.utc) - dt.timedelta(minutes=1)
        ):
            print(f"getting osu user by id {osu_id}")
            return requests.get(
                f"https://osu.ppy.sh/api/v2/users/{osu_id}/osu",
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {check_access()}",
                },
            ).json()

        if user_check:
            return user_check

    else:
        username = str(user_identifier)
        print(f"getting osu user by username {username}")
        user_check = environment.database.fetch_to_dict(
            "SELECT * FROM osu_users WHERE username = %s",
            params=(username,)
        )

        if (
                not user_check
                or user_check["last_refresh"]
                <= dt.datetime.now(tz=timezone.utc) - dt.timedelta(minutes=1)
        ):
            return requests.get(
                f"https://osu.ppy.sh/api/v2/users/{username}/osu",
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {check_access()}",
                },
            ).json()
        else:
            return user_check

    print(f"user {osu_id} already checked within last minute\n or user not found")

    return None


def extract_info(data):
    """
    extract major info from user info

    :param user_info: JSON from osu api user info
    :return: json of important user info
    """

    try:
        try:
            if data['error'] is None:
                return None
        except KeyError:
            pass

        if data:
            extracted_info = {
                'id': data['id'],
                'username': data['username'],
                'score': data['statistics']['total_score'],
                'playcount': data['statistics']['play_count'],
                'accuracy': data['statistics']['hit_accuracy'],
                'performance': data['statistics']['pp'],
                'rank': data['statistics']['global_rank'],
                'avatar': data['avatar_url'],
                'background': data['cover_url']
            }

            db = environment.database
            existing = db.fetch_one(
                "SELECT id FROM osu_users WHERE id = %s",
                params=(data['id'],)
            )

            if existing:
                db.execute(
                    """
                    UPDATE osu_users
                    SET username     = %s,
                        score        = %s,
                        playcount    = %s,
                        accuracy     = %s,
                        performance  = %s,
                        rank         = %s,
                        avatar       = %s,
                        background   = %s,
                        last_refresh = now()
                    WHERE id = %s
                    """,
                    params=(
                        extracted_info['username'],
                        extracted_info['score'],
                        extracted_info['playcount'],
                        extracted_info['accuracy'],
                        extracted_info['performance'],
                        extracted_info['rank'],
                        extracted_info['avatar'],
                        extracted_info['background'],
                        extracted_info['id']
                    )
                )
            else:
                db.execute(
                    """
                    INSERT INTO osu_users
                    (id, username, score, playcount, accuracy, performance, rank, avatar, background, last_refresh)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                    """,
                    params=(
                        extracted_info['id'],
                        extracted_info['username'],
                        extracted_info['score'],
                        extracted_info['playcount'],
                        extracted_info['accuracy'],
                        extracted_info['performance'],
                        extracted_info['rank'],
                        extracted_info['avatar'],
                        extracted_info['background'],
                    )
                )

            return extracted_info
        else:
            print("user info not found")
            return None
    except KeyError as e:
        return data


def fetch_osu_data(user_id):
    return extract_info(get_user_info(user_id))


# <editor-fold desc="osu score farm">

def get_matches():
    current_matches = environment.database.fetch_all_to_dict("SELECT * FROM osu_matches where ended = false")
    old_matches = environment.database.fetch_all_to_dict("SELECT * FROM osu_matches where ended = true")
    return {
        "current": current_matches,
        "old": old_matches
    }

# </editor-fold>
