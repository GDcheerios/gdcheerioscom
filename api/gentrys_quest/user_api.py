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


def rate_user(id: int) -> dict:
    user_items = environment.database.fetch_all_to_dict(
        """
        SELECT type, rating
        FROM gq_items
        WHERE owner = %s
        """,
        params=(id,)
    )
    if user_items:
        unweighted_rating = sum(item["rating"] for item in user_items if item.get("rating") is not None)
        weighted_rating = environment.gq_rater.get_user_rating(user_items)
        rank, tier = environment.gq_rater.get_rank(weighted_rating)

        environment.database.fetch_all_to_dict(
            """
            UPDATE gq_rankings
            SET weighted = %s, unweighted = %s, rank = %s, tier = %s
            WHERE id = %s
            RETURNING *
            """,
            params=(weighted_rating, unweighted_rating, rank, tier, id)
        )

        placement = environment.database.fetch_one(
            """
            SELECT COUNT(*) + 1
            FROM gq_rankings
            WHERE weighted > %s
            """,
            params=(weighted_rating,)
        )[0]

        environment.database.execute(
            """
            INSERT INTO gq_metrics (user_id, rank, gp)
            VALUES (%s, %s, %s)
            """,
            params=(id, placement, weighted_rating)
        )

        return {
            "weighted": weighted_rating,
            "unweighted": unweighted_rating,
            "rank": rank,
            "tier": tier,
            "placement": placement
        }

    return {
        "weighted": 0,
        "unweighted": 0,
        "rank": 'unranked',
        "tier": '1',
        "placement": 0
    }
