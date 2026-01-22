import datetime
import logging

import environment
from environment import database


def check_in(id: int):
    database.execute("UPDATE accounts SET status = 'gq_online' WHERE id = %s", params=(id,))
    return True


def check_out(id: int):
    database.execute("UPDATE accounts SET status = 'offline' WHERE id = %s", params=(id,))
    return True


def get_items(id: int):
    items = database.fetch_all_to_dict("SELECT * FROM gq_items WHERE owner = %s", params=(id,))
    return items


def get_xp_level(level: int):
    return int(environment.gq_levels[int(level) - 1])


def get_level_xp(xp: int):
    for level_xp in environment.gq_levels:
        if int(xp) < int(level_xp):
            return int(environment.gq_levels.index(level_xp) + 1)

    return len(environment.gq_levels)


def set_xp(id: int, xp: int) -> None:
    database.execute(
        "UPDATE gq_data SET xp = %s WHERE id = %s",
        params=(xp, id)
    )


def get_xp(id: int) -> dict | str:
    result = database.fetch_one("SELECT xp FROM gq_data WHERE id = %s", params=(id,))[0]
    if result is not None:
        level = get_level_xp(result)
        req_xp = get_xp_level(level + 1)

        return {
            'level': level,
            'required xp': req_xp,
            'current xp': result,
        }
    else:
        return 'user not found'


def get_placement(weighted, score):
    return environment.database.fetch_one(
        """
        SELECT COUNT(*) + 1
        FROM gq_rankings r
                 JOIN gq_data d ON d.id = r.id
        WHERE r.weighted > %s
           OR (r.weighted = %s AND d.score > %s)
        """,
        params=(weighted, weighted, score),
    )[0]


def insert_metrics(id, gp, rank):
    today = datetime.datetime.now(tz=datetime.timezone.utc).date()
    has_today_metrics = environment.database.fetch_one(
        """
        SELECT COUNT(*) > 0
        FROM gq_metrics
        WHERE user_id = %s
          AND recorded_at = %s
        """,
        params=(id, today)
    )[0]

    if not has_today_metrics:
        print(f"Inserting new gq_metrics for user_id={id}, date={today}")
        environment.database.execute(
            """
            SELECT COUNT(*) > 0
            FROM gq_metrics
            WHERE user_id = %s
              AND recorded_at = %s
            """,
            params=(id, today)
        )
    else:
        print(f"Updating existing gq_metrics for user_id={id}, date={today}")
        environment.database.execute(
            """
            UPDATE gq_metrics
            SET rank = %s,
                gp   = %s
            WHERE user_id = %s
              AND recorded_at = %s
            """,
            params=(rank, gp, id, today)
        )


def rate_user(id: int, custom_rating: int = None) -> dict:
    print(f"rate_user called for user_id={id}, custom_rating={custom_rating}")
    today = datetime.datetime.now(tz=datetime.timezone.utc).date()
    user_items = environment.database.fetch_all_to_dict(
        """
        SELECT type, rating
        FROM gq_items
        WHERE owner = %s
        """,
        params=(id,)
    )
    print(f"Fetched {len(user_items)} items for user_id={id}")
    weighted_rating = 0
    unweighted_rating = 0
    score = environment.database.fetch_one("SELECT score FROM gq_data WHERE id = %s", params=(id,))
    score = score[0] if score is not None else 0
    if custom_rating is None:
        if user_items:
            unweighted_rating = sum(item["rating"] for item in user_items if item.get("rating") is not None)
            weighted_rating = environment.gq_rater.get_user_rating(user_items)
    else:
        weighted_rating = custom_rating
        unweighted_rating = custom_rating

    print(f"Calculated ratings for user_id={id}: weighted={weighted_rating}, unweighted={unweighted_rating}")
    rank, tier = environment.gq_rater.get_rank(weighted_rating)
    print(f"Determined rank={rank}, tier={tier} for user_id={id}")

    environment.database.fetch_all_to_dict(
        """
        UPDATE gq_rankings
        SET weighted   = %s,
            unweighted = %s,
            rank       = %s,
            tier       = %s
        WHERE id = %s
        RETURNING *
        """,
        params=(weighted_rating, unweighted_rating, rank, tier, id)
    )
    print(f"Updated gq_rankings for user_id={id}")

    placement = get_placement(weighted_rating, score)
    print(f"Calculated placement={placement} for user_id={id}")
    insert_metrics(id, weighted_rating, rank)

    result = {
        "weighted": weighted_rating,
        "unweighted": unweighted_rating,
        "rank": rank,
        "tier": tier,
        "placement": placement
    }
    print(f"rate_user completed for user_id={id}, result={result}")
    return result


def get_ranking(id: int):
    data = environment.database.fetch_to_dict(
        """
        SELECT *
        FROM gq_rankings r,
             gq_data d
        WHERE r.id = %s
          and d.id = %s
        """, params=(id, id))

    placement = get_placement(data["weighted"], data["score"])
    insert_metrics(id, data["weighted"], placement)

    return {
        "placement": placement,
        "rank": data["rank"],
        "tier": data["tier"],
        "unweighted": data["unweighted"],
        "weighted": data["weighted"]
    }
