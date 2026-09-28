from environment import database
from objects.Account import Account


def get_top_players(start: int = 0, amount: int = 50):
    """
    Grabs the player ranking leaderboard

    :param start: Index of where to start.
    :param amount: How many players to grab.
    :return: Player leaderboard data.
    """
    query = f"""
        WITH ranked AS (
            SELECT
                profile.account_id,
                u.username,
                profile.weighted,
                COALESCE((
                    SELECT COALESCE(SUM(score.score), 0)
                    FROM gq.scores score
                    WHERE score.user_id = profile.account_id
                ), 0) AS score,
                profile.rank,
                profile.tier,
                ROW_NUMBER() OVER (
                    ORDER BY
                        profile.weighted DESC,
                        COALESCE((
                            SELECT COALESCE(SUM(s.score), 0)
                            FROM gq.scores s
                            WHERE s.user_id = profile.account_id
                        ), 0) DESC,
                        profile.account_id ASC
                ) AS placement
            FROM gq.profiles profile
            INNER JOIN account.users u ON profile.account_id = u.id
            INNER JOIN gq.profiles p ON profile.account_id = p.account_id
            WHERE u.status NOT IN ('restricted', 'test')
        )
        SELECT account_id, username, weighted, score, rank, tier, placement
        FROM ranked
        ORDER BY placement
        LIMIT %s OFFSET %s;
    """

    return database.fetch_all_to_dict(query, params=(amount, start))


def get_leaderboard(id, amount: int = 0, user_id: int | None = None):
    """
    Retrieves the in game leaderboard for a given leaderboard id.

    :param id: The leaderboard id.
    :param amount: how many players to grab.
    :param user_id: Optional user id whose placement should also be returned.
    :return: The leaderboard data enriched with account and gq rank info.
    """

    leaderboard_data = database.fetch_all_to_dict(
        """
        SELECT MAX(score.score) AS hs,
               score.user_id     AS account_id,
               u.username    AS username,
               profile.weighted   AS weighted,
               profile.rank       AS rank,
               profile.tier       AS tier
        FROM gq.scores score
                 LEFT JOIN account.users u ON u.id = score.user_id
                 LEFT JOIN gq.profiles profile ON profile.account_id = score.user_id
        WHERE score.leaderboard_id = %s
        GROUP BY score.user_id, u.username, profile.weighted, profile.rank, profile.tier
        ORDER BY hs DESC;
        """,
        params=(id,)
    )

    standings = None
    if leaderboard_data is not None:
        standings = []
        x = 1
        for row in leaderboard_data:
            standing = {
                "placement": x,
                "id": row.get("account_id"),
                "username": row.get("username"),
                "score": row.get("hs"),
                "weighted": row.get("weighted"),
                "rank": row.get("rank"),
                "tier": row.get("tier"),
            }

            standings.append(standing)

            if amount != 0 and x >= amount:
                break

            x += 1

    user_placement = get_placement(id, user_id) if user_id else None

    return {
        "leaderboard": standings,
        "user_placement": user_placement,
    }


def get_placement(leaderboard_id: int, user: int):
    """
    Retrieves a placement from ranking or score leaderboard with a given leaderboard and or user id.

    :param leaderboard_id: The leaderboard id
    :param user: The user id.
    """

    if leaderboard_id:
        query = """
            SELECT
                score.user_id AS id,
                u.username AS username,
                MAX(score.score) AS score,
                profile.weighted AS weighted,
                profile.rank AS rank,
                profile.tier AS tier,
                (
                    SELECT COUNT(*) + 1
                    FROM gq.scores s2
                    WHERE s2.leaderboard_id = score.leaderboard_id
                      AND s2.score > MAX(score.score)
                ) AS placement
            FROM gq.scores score
            LEFT JOIN account.users u ON u.id = score.user_id
            LEFT JOIN gq.profiles profile ON profile.account_id = score.user_id
            WHERE score.leaderboard_id = %s
              AND score.user_id = %s
            GROUP BY score.leaderboard_id, score.user_id, u.username, profile.weighted, profile.rank, profile.tier
            LIMIT 1
        """
        params = (leaderboard_id, user)
    else:
        query = """
            SELECT
                profile.id AS id,
                u.username AS username,
                profile.weighted AS weighted,
                profile.rank AS rank,
                profile.tier AS tier,
                (
                    SELECT COUNT(*) + 1
                    FROM gq.profiles r2
                    WHERE r2.weighted > profile.weighted
                ) AS placement
            FROM gq.profiles profile
            LEFT JOIN account.users u ON u.id = profile.account_id
            WHERE profile.account_id = %s
            LIMIT 1
        """
        params = (user,)

    return database.fetch_to_dict(query, params=params)


def submit_leaderboard(leaderboard_id: int, user: int, score: int, visitation: str):
    """
    Submits a score to the leaderboard.

    :param leaderboard_id: Leaderboard id.
    :param user: User ID.
    :param score: Score.
    :param visitation: Visitation UUID.
    :return: Object with username and score.
    """

    user = Account(user)
    if database.fetch_one("select online from gq.leaderboards where id = %s", params=(leaderboard_id,))[0]:
        database.execute(
            "INSERT INTO gq.scores (name, score, leaderboard_id, user_id, visitation_id) values (%s, %s, %s, %s, %s);",
            params=(user.username, int(score), int(leaderboard_id), user.id, visitation))

    return {
        "username": user.username,
        "score": score
    }
