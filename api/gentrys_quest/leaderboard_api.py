from environment import database
from objects import Account


def get_top_players(start: int = 0, amount: int = 50, online: bool = False):
    """
    Grabs the player ranking leaderboard

    :param start: Index of where to start.
    :param amount: How many players to grab.
    :param online: If only grabbing online players.
    :return: Player leaderboard data.
    """
    query = f"""
                SELECT gq_rankings.id, accounts.username,
                gq_rankings.weighted, gq_rankings.rank, gq_rankings.tier
                FROM gq_rankings
                INNER JOIN accounts ON gq_rankings.id = accounts.id
                INNER JOIN gq_data d ON gq_rankings.id = d.id
                WHERE accounts.status NOT IN ('restricted', 'test') {f"AND accounts.status = 'gq_online'" if online else ""}
                ORDER BY weighted desc
                LIMIT %s OFFSET %s;
            """

    players = database.fetch_all_to_dict(query, params=(amount, start))

    if players is not None:
        placement = start + 1
        for player in players:
            player["placement"] = placement
            placement += 1

    return players


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
        SELECT MAX(gs.score) AS hs,
               gs."user"     AS account_id,
               a.username    AS username,
               gr.weighted   AS weighted,
               gr.rank       AS rank,
               gr.tier       AS tier
        FROM gq_scores gs
                 LEFT JOIN accounts a ON a.id = gs."user"
                 LEFT JOIN gq_rankings gr ON gr.id = gs."user"
        WHERE gs.leaderboard = %s
        GROUP BY gs."user", a.username, gr.weighted, gr.rank, gr.tier
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
                gs."user" AS id,
                a.username AS username,
                MAX(gs.score) AS score,
                gr.weighted AS weighted,
                gr.rank AS rank,
                gr.tier AS tier,
                (
                    SELECT COUNT(*) + 1
                    FROM gq_scores s2
                    WHERE s2.leaderboard = gs.leaderboard
                      AND s2.score > MAX(gs.score)
                ) AS placement
            FROM gq_scores gs
            LEFT JOIN accounts a ON a.id = gs."user"
            LEFT JOIN gq_rankings gr ON gr.id = gs."user"
            WHERE gs.leaderboard = %s
              AND gs."user" = %s
            GROUP BY gs.leaderboard, gs."user", a.username, gr.weighted, gr.rank, gr.tier
            LIMIT 1
        """
        params = (leaderboard_id, user)
    else:
        query = """
            SELECT
                gr.id AS id,
                a.username AS username,
                gr.weighted AS weighted,
                gr.rank AS rank,
                gr.tier AS tier,
                (
                    SELECT COUNT(*) + 1
                    FROM gq_rankings r2
                    WHERE r2.weighted > gr.weighted
                ) AS placement
            FROM gq_rankings gr
            LEFT JOIN accounts a ON a.id = gr.id
            WHERE gr.id = %s
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
    if database.fetch_one("select online from gq_leaderboards where id = %s", params=(leaderboard_id,))[0]:
        database.execute(
            "INSERT INTO gq_scores (name, score, leaderboard, \"user\", visitation) values (%s, %s, %s, %s, %s);",
            params=(user.username, int(score), int(leaderboard_id), user.id, visitation))

    return {
        "username": user.username,
        "score": score
    }
