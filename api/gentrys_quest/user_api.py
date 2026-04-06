import datetime
import logging

import environment
from environment import database
from utils.logger import setup_logger

logger = setup_logger("api.gentrys_quest.user")


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


def get_placement(user_id: int):
    row = environment.database.fetch_one(
        """
        SELECT placement
        FROM (
            SELECT
                r.id,
                ROW_NUMBER() OVER (
                    ORDER BY
                        r.weighted DESC,
                        COALESCE((
                            SELECT COALESCE(SUM(s.score), 0)
                            FROM gq_scores s
                            WHERE s."user" = r.id
                        ), 0) DESC,
                        r.id ASC
                ) AS placement
            FROM gq_rankings r
        ) ranked
        WHERE id = %s
        """,
        params=(user_id,),
    )
    return row[0] if row else None


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
        logger.debug("Inserting new gq_metrics for user_id=%s, date=%s", id, today)
        environment.database.execute(
            """
            INSERT INTO gq_metrics (user_id, rank, gp, recorded_at)
            VALUES (%s, %s, %s, %s)
            """,
            params=(id, rank, gp, today)
        )
    else:
        logger.debug("Updating existing gq_metrics for user_id=%s, date=%s", id, today)
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
    logger.debug("rate_user called for user_id=%s, custom_rating=%s", id, custom_rating)
    today = datetime.datetime.now(tz=datetime.timezone.utc).date()
    user_items = environment.database.fetch_all_to_dict(
        """
        SELECT type, rating
        FROM gq_items
        WHERE owner = %s
        """,
        params=(id,)
    )
    logger.debug("Fetched %s items for user_id=%s", len(user_items), id)
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

    logger.debug(
        "Calculated ratings for user_id=%s: weighted=%s, unweighted=%s",
        id,
        weighted_rating,
        unweighted_rating,
    )
    rank, tier = environment.gq_rater.get_rank(weighted_rating)
    logger.debug("Determined rank=%s, tier=%s for user_id=%s", rank, tier, id)

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
    logger.debug("Updated gq_rankings for user_id=%s", id)

    placement = get_placement(id)
    logger.debug("Calculated placement=%s for user_id=%s", placement, id)
    insert_metrics(id, weighted_rating, rank)

    result = {
        "weighted": weighted_rating,
        "unweighted": unweighted_rating,
        "rank": rank,
        "tier": tier,
        "placement": placement
    }
    logger.debug("rate_user completed for user_id=%s, result=%s", id, result)
    return result


def get_score(id: int) -> int:
    result = database.fetch_one(
        'SELECT COALESCE(SUM(score), 0) FROM gq_scores WHERE "user" = %s',
        params=(id,)
    )[0]
    return int(result)


def get_money(id: int):
    result = environment.database.fetch_one("SELECT money FROM gq_data WHERE id = %s", params=(id,))[0]
    return result if result is not None else 0


def get_ranking(id: int):
    data = environment.database.fetch_to_dict(
        """
        SELECT *
        FROM gq_rankings r,
             gq_data d
        WHERE r.id = %s
          and d.id = %s
        """, params=(id, id))

    if data is None:
        environment.database.execute(
            """
            INSERT INTO gq_rankings (id)
            VALUES (%s)
            ON CONFLICT (id) DO NOTHING
            """,
            params=(id,),
        )
        data = environment.database.fetch_to_dict(
            """
            SELECT *
            FROM gq_rankings r,
                 gq_data d
            WHERE r.id = %s
              and d.id = %s
            """,
            params=(id, id),
        )

    if data is None:
        return {
            "placement": None,
            "rank": None,
            "tier": None,
            "unweighted": 0,
            "weighted": 0,
        }

    placement = get_placement(id)
    if placement is not None:
        insert_metrics(id, data["weighted"], placement)

    return {
        "placement": placement,
        "rank": data["rank"],
        "tier": data["tier"],
        "unweighted": data["unweighted"],
        "weighted": data["weighted"]
    }
