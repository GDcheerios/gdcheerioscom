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
