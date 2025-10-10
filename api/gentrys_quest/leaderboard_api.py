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
                WHERE accounts.status NOT IN ('restricted', 'test') {f"AND accounts.status = 'gq_online'" if online else ""}
                ORDER BY weighted desc
                LIMIT %s OFFSET %s;
            """

    return database.fetch_all_to_dict(query, params=(amount, start))


def get_leaderboard(id, amount: int = 0):
    """
    Retrieves the in game leaderboard for a given leaderboard id.

    :param id: The leaderboard id.
    :param amount: how many players to grab.
    :return: The leaderboard data enriched with account and gq rank info.
    """

    leaderboard_data = database.fetch_all_to_dict(
        """
        SELECT 
            MAX(gs.score) AS hs,
            gs."user"      AS account_id,
            a.username     AS username,
            gr.weighted    AS weighted,
            gr.rank        AS rank,
            gr.tier        AS tier
        FROM gq_scores gs
        LEFT JOIN accounts a ON a.id = gs."user"
        LEFT JOIN gq_rankings gr ON gr.id = gs."user"
        WHERE gs.leaderboard = %s
        GROUP BY gs."user", a.username, gr.weighted, gr.rank, gr.tier
        ORDER BY hs DESC;
        """,
        params=(id,)
    )

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

        return standings


def submit_leaderboard(leaderboard_id: int, user: int, score: int):
    """
    Submits a score to the leaderboard.

    :param leaderboard_id: Leaderboard id.
    :param user: User ID.
    :param score: Score.
    :return: Object with username and score.
    """

    user = Account(user)
    if database.fetch_one("select online from gq_leaderboards where id = %s", params=(leaderboard_id,))[0]:
        database.execute("INSERT INTO gq_scores (name, score, leaderboard, \"user\") values (%s, %s, %s, %s);",
                         params=(user.username, int(score), int(leaderboard_id), user.id))

    return {
        "username": user.username,
        "score": score
    }
