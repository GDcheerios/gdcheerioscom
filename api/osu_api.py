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


def compare_to_match(user, match_id: int) -> dict:
    if not match_id:
        return user

    match = environment.database.fetch_to_dict("SELECT * FROM osu.matches WHERE id = %s", params=(match_id,))

    match_user = environment.database.fetch_to_dict(
        """
        SELECT *
        FROM osu.match_users
        WHERE user_id = %s
          AND match_id = %s
        """,
        params=(user["id"], match_id)
    )

    reconstructed_pp = environment.database.fetch_one(
        """
        WITH scores AS (SELECT pp,
                               rank,
                               ROW_NUMBER() OVER (ORDER BY pp DESC) AS rank_index
                        FROM osu.scores
                        WHERE user_id = %s
                          AND submitted_at >= %s
                          AND submitted_at <= COALESCE(%s::timestamp, NOW())
                          AND rank != 'F'
                        LIMIT 100),
             calc_pp AS (SELECT COALESCE(SUM(pp * POWER(0.95, rank_index - 1)), 0) AS total_pp
                         FROM scores)
        UPDATE osu.match_users
        SET reconstructed_pp = calc_pp.total_pp
        FROM calc_pp
        WHERE user_id = %s
          AND match_id = %s
        RETURNING reconstructed_pp
        """,
        params=(
            user["id"],
            match["started_at"],
            match["ended_at"],
            user["id"],
            match["id"]
        )
    )
    if not match_user:
        return user

    ended_stats = match_user["ending_stats"]

    stats = (
        user if ended_stats is None else ended_stats,
        match_user["starting_stats"]
    )

    placement = environment.database.fetch_one(
        """
        WITH match AS (
            SELECT *
            FROM osu.matches
            WHERE id = %s
        ),
             ranked_users AS (
                 SELECT mu.user_id,
                        mu.placement AS old_placement,
                        CASE LOWER(TRIM(m.objective))
                            WHEN 'reconstructed_pp'
                                THEN DENSE_RANK() OVER (ORDER BY mu.reconstructed_pp DESC)
                            ELSE DENSE_RANK() OVER (
                                ORDER BY (to_jsonb(u) ->> m.objective)::numeric -
                                         (mu.starting_stats ->> m.objective)::numeric DESC
                                )
                            END AS new_placement
                 FROM osu.match_users mu
                          JOIN match m ON mu.match_id = m.id
                          JOIN osu.users u ON mu.user_id = u.id
             ),
             updated_users AS (
                 UPDATE osu.match_users AS mu
                     SET placement = ru.new_placement
                     FROM ranked_users ru, match m
                     WHERE mu.user_id = ru.user_id
                         AND mu.match_id = m.id
                     RETURNING mu.user_id, ru.new_placement, ru.old_placement
             )
        SELECT new_placement, old_placement
        FROM updated_users
        WHERE user_id = %s;
        """,
        params=(match_id, user["id"])
    )

    placement_map = []

    if placement[0] != placement[1]:
        placement_map = environment.database.fetch_all(
            """
            SELECT user_id, placement
            FROM osu.match_users
            WHERE match_id = %s
                AND placement >= %s
                AND placement <= %s
            """,
            params=(match_id, min(placement), max(placement))
        )

    user = {
        "id": user["id"],
        "username": user["username"],
        "nickname": match_user["nickname"],
        "total_score": stats[0].get("total_score", 0) - stats[1].get("total_score", 0),
        "ranked_score": stats[0].get("ranked_score", 0) - stats[1].get("ranked_score", 0),
        "total_hits": stats[0].get("total_hits", 0) - stats[1].get("total_hits", 0),
        "playcount": stats[0].get("playcount", 0) - stats[1].get("playcount", 0),
        "accuracy": float(stats[0].get("accuracy", 0)) - float(stats[1].get("accuracy", 0)),
        "pp": stats[0].get("pp", 0) - stats[1].get("pp", 0),
        "global_rank": (stats[0].get("global_rank", 0) or 0) - (stats[1].get("global_rank", 0) or 0),
        "country_rank": (stats[0].get("country_rank", 0) or 0) - (stats[1].get("country_rank", 0) or 0),
        "grade_ss": stats[0].get("grade_ss", 0) - stats[1].get("grade_ss", 0),
        "grade_ssh": stats[0].get("grade_ssh", 0) - stats[1].get("grade_ssh", 0),
        "grade_s": stats[0].get("grade_s", 0) - stats[1].get("grade_s", 0),
        "grade_sh": stats[0].get("grade_sh", 0) - stats[1].get("grade_sh", 0),
        "grade_a": stats[0].get("grade_a", 0) - stats[1].get("grade_a", 0),
        "avatar": user["avatar"],
        "team": environment.database.fetch_to_dict("SELECT * FROM osu.teams WHERE id = %s",
                                                   params=(match_user["team_id"],)) if match_user['team_id'] else None,
        "reconstructed_pp": reconstructed_pp,
        "placement": placement[0] if placement is not None else 0,
        "placement_map": placement_map,
        "ended_stats": ended_stats,
        "averages": {
            "score": get_average_metric_by_score(match_id, user["id"], "score"),
            "pp": get_average_metric_by_score(match_id, user["id"], "pp"),
            "accuracy": get_average_metric_by_score(match_id, user["id"], "accuracy")
        },
        "background": user["background"]
    }

    environment.database.execute(
        """
        INSERT INTO osu.match_metrics (match_id, user_id, placement, objective, plays, date)
        VALUES (%s, %s, %s, %s, %s, CURRENT_DATE)
        ON CONFLICT (match_id, user_id, date)
            DO UPDATE SET
                placement = EXCLUDED.placement,
                objective = EXCLUDED.objective,
                plays = EXCLUDED.plays;
        """,
        params=(
            match_id,
            user["id"],
            placement[0],
            user[match["objective"]],
            user["playcount"]
        )
    )

    return user


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
            <= dt.datetime.now(tz=timezone.utc) - dt.timedelta(minutes=environment.osu_refresh_cooldown)
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
                f"https://osu.ppy.sh/api/v2/users/{user_identifier}/scores/recent",
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

            try:
                return {
                    'user': user_req,
                    'score': recent_score_req[0]
                }
            except KeyError:
                return {
                    'user': user_req,
                    'score': None
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
            last_refresh = user_info.get('last_refresh')
            if last_refresh:
                next_refresh = last_refresh + dt.timedelta(minutes=environment.osu_refresh_cooldown)
            else:
                next_refresh = dt.datetime.now(tz=timezone.utc) + dt.timedelta(
                    minutes=environment.osu_refresh_cooldown)

            next_refresh = next_refresh.isoformat()

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
                'background': user_info['cover_url'],
                'next_refresh': next_refresh
            }

            db = environment.database
            if data['score'] is None:
                data['score'] = {"id": 0}

            exists = db.fetch_to_dict(
                """
                SELECT EXISTS(SELECT 1 FROM osu.users WHERE id = %s)  as "user",
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
                    INSERT INTO osu.scores (id, beatmap_id, user_id, submitted_at, accuracy, rank, pp, score, cover,
                                            title, artist)
                    VALUES (%s, %s, %s, now(), %s, %s, %s, %s, %s, %s, %s)
                    """,
                    params=(
                        data['score']['id'],
                        data['score']['beatmap']['id'],
                        data['user']['id'],
                        data['score']['accuracy'],
                        data['score']['rank'],
                        data['score']['pp'],
                        data['score']['classic_total_score'],
                        data['score']['beatmapset']['covers']['cover'],
                        data['score']['beatmapset']['title'],
                        data['score']['beatmapset']['artist']
                    )
                )

            score = None
            if data['score']['id'] != 0:
                score = {
                    'score': data['score']['classic_total_score'],
                    'pp': data['score']['pp'],
                    'beatmap_id': data['score']['beatmap']['id'],
                    'id': data['score']['id'],
                    'accuracy': data['score']['accuracy'],
                    'rank': data['score']['rank'],
                    'cover': data['score']['beatmapset']['covers']['cover'],
                    'title': data['score']['beatmapset']['title'],
                    'artist': data['score']['beatmapset']['artist']
                }

            info = {
                'user': extracted_info,
                'score': score
            }

            return info
        else:
            logger.warning("user info not found")
            return None
    except KeyError as e:

        return data


def fetch_osu_data(user_id, skip_api=False, match_id=None):
    result = extract_info(get_user_info(user_id, skip_api=skip_api))
    if match_id:
        result["user"] = compare_to_match(result["user"], match_id)

    return result


def get_team(id):
    team = environment.database.fetch_to_dict(
        """
        SELECT t.*,
               COALESCE(SUM(
                       CASE LOWER(TRIM(m.objective))
                           WHEN 'reconstructed_pp' THEN mu.reconstructed_pp
                           ELSE
                               (to_jsonb(u) ->> m.objective)::numeric
                                   - (mu.starting_stats ->> m.objective)::numeric
                           END
               ), 0) AS points

        FROM osu.teams t
                 LEFT JOIN osu.match_users mu ON t.id = mu.team_id
                 LEFT JOIN osu.users u ON u.id = mu.user_id
                 LEFT JOIN osu.matches m ON m.id = mu.match_id
        WHERE t.id = %s
        GROUP BY t.id
        """,
        params=(id,)
    )
    return team


def get_team_users(id, limit: int = 20):
    return [user[0] for user in environment.database.fetch_all(
        """
        SELECT user_id FROM osu.match_users
        WHERE team_id = %s
        ORDER BY placement
        LIMIT %s
        """,
        params=(id, limit)
    )]


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


def get_recent_scores(match_id: int, limit: int = 5):
    return environment.database.fetch_all(
        """
        WITH match AS (SELECT *
                       FROM osu.matches
                       WHERE id = %s),
             match_users AS (SELECT mu.user_id,
                                    mu.match_id
                             FROM osu.match_users mu,
                                  match m
                             WHERE mu.match_id = m.id)
        SELECT s.id
        FROM osu.scores s,
             match_users,
             match
        WHERE s.user_id = match_users.user_id
          and s.submitted_at > match.started_at
          and s.submitted_at <= COALESCE(match.ended_at::timestamp, NOW())
        ORDER BY s.submitted_at DESC
        LIMIT %s
        """,
        params=(match_id, limit)
    )


def get_best_scores(match_id: int, limit: int = 5):
    return environment.database.fetch_all(
        """
        WITH match AS (
            SELECT *
            FROM osu.matches
            WHERE id = %s
        )
        SELECT s.id
        FROM osu.scores s,
             match
        WHERE s.submitted_at > match.started_at
          AND s.submitted_at <= COALESCE(match.ended_at::timestamp, NOW())
          AND s.user_id IN (
            SELECT DISTINCT user_id
            FROM osu.match_events
            WHERE match_id = match.id
              AND user_id IS NOT NULL
        )
        ORDER BY (
                     COALESCE(
                             (
                                 to_json(s.*) ->>
                                 CASE LOWER(TRIM(match.objective::text))
                                     WHEN 'reconstructed_pp' THEN 'pp'
                                     WHEN 'total_score' THEN 'score'
                                     WHEN 'ranked_score' THEN 'score'
                                     ELSE LOWER(TRIM(match.objective::text))
                                     END
                                 )::numeric,
                             0
                     )
                     ) DESC
        LIMIT %s
        """,
        params=(match_id, limit),
    )


def get_average_metric_by_score(match_id: int, user_id: int, metric: str = "accuracy", limit: int = 100):
    return environment.database.fetch_one(
        """
        WITH match AS (SELECT *
                       from osu.matches
                       WHERE id = %s),
             scores AS (SELECT *
                        from osu.scores
                                 CROSS JOIN match m
                        WHERE user_id = %s
                          and submitted_at > m.started_at
                          and submitted_at <= COALESCE(m.ended_at::timestamp, NOW())
                        LIMIT %s)
        SELECT CASE
                   WHEN %s = 'pp' THEN AVG(nullif(s.pp, 0))
                   WHEN %s = 'accuracy' THEN AVG(s.accuracy)
                   WHEN %s = 'score' THEN AVG(s.score)
                   ELSE 0
                   END
        FROM scores s
        """,
        params=(match_id, user_id, limit, metric, metric, metric)
    )[0]

# </editor-fold>
