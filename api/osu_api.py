import requests
import datetime as dt
from datetime import timezone
import traceback

import environment
from utils.logger import setup_logger

logger = setup_logger("api.osu")

expiration = 0
token = 0


def client_grant():
    global expiration
    global token
    logger.info("granting client token")
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
    logger.info("checking access")
    dt_obj = dt.datetime.now()

    try:
        if round(dt_obj.microsecond / 1000) > expiration:
            logger.info("renewing token")
            token = client_grant()

    except Exception as E:
        logger.exception("error checking osu access token: %s", E)
        token = client_grant()

    return token


def get_user_info(user_identifier, skip_api=False):
    """
    Retrieve osu api user info.

    If `user_identifier` can be cast to int, it is treated as a numeric osu ID.
    Otherwise, it is treated as a username.
    """

    user_check = environment.database.fetch_to_dict(
        """
        SELECT *
        FROM osu.users
        WHERE id::text = %s
           OR username::text = %s
        """,
        params=(str(user_identifier), str(user_identifier))
    )

    if (
            not user_check
            or user_check["last_refresh"]
            <= dt.datetime.now(tz=timezone.utc) - dt.timedelta(minutes=1)
    ):
        if not skip_api:
            logger.info("getting osu user %s", user_identifier)
            user_req = requests.get(
                f"https://osu.ppy.sh/api/v2/users/{user_identifier}/osu",
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {check_access()}",
                },
            ).json()
            recent_score_req = requests.get(
                f"https://osu.ppy.sh/api/v2/users/{user_req['id']}/scores/recent",
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {check_access()}",
                    "x-api-version": "20220705"
                },
                params={
                    "mode": "osu",
                    "limit": 1,
                    "include_fails": "1"
                }
            ).json()

            if len(recent_score_req) == 0:
                return {
                    'user': user_req,
                    'score': None
                }

            return {
                'user': user_req,
                'score': recent_score_req[0]
            }

    if user_check:
        score_check = environment.database.fetch_to_dict(
            """
            SELECT *
            FROM osu.scores
            WHERE user_id = %s
            ORDER BY submitted_at DESC
            LIMIT 1
            """,
            (user_check['id'],)
        )
        return {
            'user': user_check,
            'score': score_check
        }

    logger.info("user %s already checked within last minute or user not found", user_identifier)

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
            user_info = data['user']
            extracted_info = {
                'id': user_info['id'],
                'username': user_info['username'],
                'total_score': user_info['statistics']['total_score'],
                'ranked_score': user_info['statistics']['ranked_score'],
                'total_hits': user_info['statistics']['total_hits'],
                'playcount': user_info['statistics']['play_count'],
                'accuracy': user_info['statistics']['hit_accuracy'],
                'pp': user_info['statistics']['pp'],
                'global_rank': user_info['statistics']["global_rank"],
                'country_rank': user_info['statistics']['country_rank'],
                'grade_ss': user_info['statistics']['grade_counts']['ss'],
                'grade_ssh': user_info['statistics']['grade_counts']['ssh'],
                'grade_s': user_info['statistics']['grade_counts']['s'],
                'grade_sh': user_info['statistics']['grade_counts']['sh'],
                'grade_a': user_info['statistics']['grade_counts']['a'],
                'avatar': user_info['avatar_url'],
                'background': user_info['cover_url']
            }

            db = environment.database
            if data['score'] is None:
                data['score'] = {"id": 0}

            exists = db.fetch_to_dict(
                """
                SELECT EXISTS(SELECT 1 FROM osu.users WHERE id = %s)          as "user",
                       EXISTS(SELECT 1 FROM osu.scores WHERE id = %s) as score
                """,
                params=(data['user']['id'], data['score']['id'])
            )

            if exists['user']:
                db.execute(
                    """
                    UPDATE osu.users
                    SET username     = %s,
                        total_score  = %s,
                        ranked_score = %s,
                        total_hits   = %s,
                        playcount    = %s,
                        accuracy     = %s,
                        pp           = %s,
                        global_rank  = %s,
                        country_rank = %s,
                        grade_ss     = %s,
                        grade_ssh    = %s,
                        grade_s      = %s,
                        grade_sh     = %s,
                        grade_a      = %s,
                        avatar       = %s,
                        background   = %s,
                        last_refresh = now()
                    WHERE id = %s
                    """,
                    params=(
                        extracted_info.get('username') or '',
                        extracted_info.get('total_score') or 0,
                        extracted_info.get('ranked_score') or 0,
                        extracted_info.get('total_hits') or 0,
                        extracted_info.get('playcount') or 0,
                        extracted_info.get('accuracy') or 0,
                        extracted_info.get('pp') or 0,
                        extracted_info.get('global_rank') or 0,
                        extracted_info.get('country_rank') or 0,
                        extracted_info.get('grade_ss') or 0,
                        extracted_info.get('grade_ssh') or 0,
                        extracted_info.get('grade_s') or 0,
                        extracted_info.get('grade_sh') or 0,
                        extracted_info.get('grade_a') or 0,
                        extracted_info.get('avatar') or '',
                        extracted_info.get('background') or '',
                        extracted_info.get('id')
                    )
                )
            else:
                db.execute(
                    """
                    INSERT INTO osu.users
                    (id, username, total_score, ranked_score, total_hits, playcount, accuracy, pp, global_rank,
                     country_rank, grade_ss, grade_ssh, grade_s, grade_sh, grade_a, avatar, background, last_refresh)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                    """,
                    params=(
                        extracted_info.get('id'),
                        extracted_info.get('username') or '',
                        extracted_info.get('total_score') or 0,
                        extracted_info.get('ranked_score') or 0,
                        extracted_info.get('total_hits') or 0,
                        extracted_info.get('playcount') or 0,
                        extracted_info.get('accuracy') or 0,
                        extracted_info.get('pp') or 0,
                        extracted_info.get('global_rank') or 0,
                        extracted_info.get('country_rank') or 0,
                        extracted_info.get('grade_ss') or 0,
                        extracted_info.get('grade_ssh') or 0,
                        extracted_info.get('grade_s') or 0,
                        extracted_info.get('grade_sh') or 0,
                        extracted_info.get('grade_a') or 0,
                        extracted_info.get('avatar') or '',
                        extracted_info.get('background') or '',
                    )
                )

            if not exists["score"] and data['score']['id'] != 0:
                db.execute(
                    """
                    INSERT INTO osu.scores (id, beatmap_id, user_id, submitted_at, accuracy, rank, pp, score)
                    VALUES (%s, %s, %s, now(), %s, %s, %s, %s)
                    """,
                    params=(
                        data['score']['id'],
                        data['score']['beatmap']['id'],
                        data['user']['id'],
                        data['score']['accuracy'],
                        data['score']['rank'],
                        data['score']['pp'],
                        data['score']['classic_total_score'],
                    )
                )

            return extracted_info
        else:
            logger.warning("user info not found")
            return None
    except KeyError as e:
        return data['user']


def fetch_osu_data(user_id, skip_api=False):
    return extract_info(get_user_info(user_id, skip_api=skip_api))


# <editor-fold desc="osu score farm">

def get_matches():
    matches = environment.database.fetch_all_to_dict(
        """
        SELECT id,
               name,
               open,
               pinned,
               ended,
               started_at,
               opener_id,
               ended_at,
               (select username
                from account.users
                where id = opener_id)            as creator,
               (select count(*)
                from osu.match_users
                where match_id = osu.matches.id) as users
        FROM osu.matches
        """
    )
    current_matches = []
    old_matches = []
    for match in matches:
        if match["ended"]:
            old_matches.append(match)
        else:
            current_matches.append(match)

    old_matches.sort(key=lambda x: x["started_at"], reverse=True)
    old_matches.sort(key=lambda x: x["pinned"], reverse=True)
    current_matches.sort(key=lambda x: x["started_at"], reverse=True)
    current_matches.sort(key=lambda x: x["pinned"], reverse=True)
    return {
        "current": current_matches,
        "old": old_matches
    }

# </editor-fold>
