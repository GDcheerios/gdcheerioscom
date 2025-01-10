from environment import database
from objects import Account


def leaderboard(start: int, amount: int, online: bool):
    """
    Grabs the player ranking leaderboard

    :param start: Index of where to start.
    :param amount: How many players to grab.
    :param online: If only grabbing online players.
    :return: Player leaderboard data.
    """
    query = f"""
                SELECT rankings.id, accounts.username,
                rankings.c_weighted, rankings.c_rank, rankings.c_tier
                FROM rankings
                INNER JOIN accounts ON rankings.id = accounts.id
                WHERE accounts.status NOT IN ('restricted', 'test') {f"AND accounts.status = 'gqc_online'" if online else ""}
                ORDER BY c_weighted desc
                LIMIT %s OFFSET %s;
            """

    return database.fetch_all(query, params=(amount, start))


def ig_leaderboard(id):
    """
    Retrieves the in game leaderboard for a given leaderboard id.

    :param id: The leaderboard id.
    :return: The leaderboard data.
    """

    leaderboard = database.fetch_all(
        "SELECT name, MAX(score) as hs FROM leaderboard_scores WHERE leaderboard = %s GROUP BY name ORDER BY hs DESC;",
        params=(id,))
    standings = []
    x = 1
    for standing in leaderboard:
        standing = {
            "placement": x,
            "username": standing[0],
            "score": standing[1]
        }
        standings.append(standing)

        x += 1

    return standings


def submit_leaderboard(leaderboard: int, user: int, score: int):
    """
    Submits a score to the leaderboard.

    :param leaderboard: Leaderboard id.
    :param user: User ID.
    :param score: Score.
    :return: Object with username and score.
    """

    user = Account(user)
    if database.fetch_one("select online from leaderboards where id = %s", params=leaderboard)[0]:
        database.execute("INSERT INTO leaderboard_scores (name, score, leaderboard, \"user\") values (%s, %s, %s, %s);",
                         params=(user.username, int(score), int(leaderboard), user.id))

    return {
        "username": user.username,
        "score": score
    }
