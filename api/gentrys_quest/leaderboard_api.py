from environment import database
from objects import Account


def leaderboard(start: int = 0, amount: int = 50, online: bool = False):
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
                WHERE accounts.status NOT IN ('restricted', 'test') {f"AND accounts.status = 'gqc_online'" if online else ""}
                ORDER BY weighted desc
                LIMIT %s OFFSET %s;
            """

    return database.fetch_all(query, params=(amount, start))


def in_game_leaderboard(id, amount: int = 0, commas: bool = False):
    """
    Retrieves the in game leaderboard for a given leaderboard id.

    :param id: The leaderboard id.
    :param amount: how many players to grab.
    :param commas: if the score should be formatted with commas.
    :return: The leaderboard data.
    """

    leaderboard_data = database.fetch_all(
        "SELECT name, MAX(score) as hs FROM gq_scores WHERE leaderboard = %s GROUP BY name ORDER BY hs DESC;",
        params=(id,))

    if leaderboard_data is not None:
        standings = []
        x = 1
        for standing in leaderboard_data:
            standing = {
                "placement": x,
                "username": standing[0],
                "score": standing[1]
            }

            if commas:
                standing["score"] = "{:,}".format(standing["score"])

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
