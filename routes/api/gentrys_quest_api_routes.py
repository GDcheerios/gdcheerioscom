import json
from flask import Blueprint, request

import environment

from api.gentrys_quest import leaderboard_api, user_api
from api.key_api import require_scopes

from objects import Account

gentrys_quest_api_blueprint = Blueprint("gentrys_quest_api_blueprint", __name__)


# region Version
@gentrys_quest_api_blueprint.get("/gq/get-version")
def version(): return environment.gq_version


@gentrys_quest_api_blueprint.post("/gq/set-version")
def set_version():
    if environment.secret == request.form.get("secret"):
        environment.database.execute(
            f"UPDATE server SET version = %s",
            params=(request.form.get("version"),)
        )


# endregion

# region Users
@gentrys_quest_api_blueprint.get("/gq/check-in/<id>")
def check_in(id: int):
    return user_api.check_in(id)


@gentrys_quest_api_blueprint.get("/gq/check-out/<id>")
def check_out(id: int): return user_api.check_out(id)


@gentrys_quest_api_blueprint.get("/gq/get-items/<id>")
@require_scopes(["account:read"])
def get_items(id: int): return {'items': user_api.get_items(id)}


@gentrys_quest_api_blueprint.get("gq/set-xp/<id>/<xp>")
@require_scopes(["account:write"])
def set_xp(id, xp):
    user_api.set_xp(int(id), int(xp))
    return user_api.get_xp(id)


@gentrys_quest_api_blueprint.get("gq/get-xp/<id>")
@require_scopes(["account:read"])
def get_xp(id): return user_api.get_xp(int(id))


@gentrys_quest_api_blueprint.get("/gq/get/<id>")
@require_scopes(["account:read"])
def get(id: int): return Account(id).jsonify()["gq data"]


@gentrys_quest_api_blueprint.post("/gq/create/")
@require_scopes(["account:write"])
def gq_create():
    data = request.json
    check = environment.database.fetch_one("SELECT id FROM gq_data WHERE id = %s", params=(data["ID"],))
    if check is None:
        environment.database.execute(
            "INSERT INTO gq_data (id, money, score) VALUES (%s, 0, 0)",
            params=(data["ID"],)
        )
        return "Success", 200

    return "User already exists", 400


@gentrys_quest_api_blueprint.post("/gq/add-item/")
@require_scopes(["account:write"])
def add_item():
    data = request.json
    metadata_json = json.dumps(data["item"])
    rating = environment.gq_rater.get_rating(data["type"], data["item"])
    item_data = environment.database.fetch_to_dict(
        """
        INSERT INTO gq_items (type, metadata, owner, rating)
        VALUES (%s, %s::jsonb, %s, %s)
        RETURNING *
        """,
        params=(data["type"], metadata_json, data["owner"], rating)
    )
    item_data["metadata"]["ID"] = item_data["id"]
    environment.database.execute(
        """
        UPDATE gq_items
        SET metadata = %s::jsonb
        WHERE id = %s
        """,
        params=(json.dumps(item_data["metadata"]), item_data["id"])
    )
    ranking = user_api.rate_user(data["owner"])
    return {
        "ranking": ranking,
        "item": item_data
    }


@gentrys_quest_api_blueprint.post("/gq/update-item/")
@require_scopes(["account:write"])
def update_item():
    data = request.json
    metadata_json = json.dumps(data["item"])
    rating = environment.gq_rater.get_rating(data["type"], data["item"])
    item_data = environment.database.fetch_to_dict(
        """
        UPDATE gq_items
        SET metadata = %s::jsonb,
            rating   = %s
        WHERE id = %s
        RETURNING *
        """,
        params=(metadata_json, rating, data["item"]["ID"])
    )
    ranking = user_api.rate_user(item_data["owner"])
    return {
        "ranking": ranking,
        "item": item_data
    }


@gentrys_quest_api_blueprint.post("/gq/remove-item/<id>")
@require_scopes(["account:write"])
def remove_item(id):
    owner = environment.database.fetch_one("SELECT owner FROM gq_items WHERE id = %s", params=(id,))
    if owner:
        owner = owner[0]

    environment.database.execute(
        """
        DELETE
        FROM gq_items
        WHERE id = %s
        """,
        params=(id,)
    )
    ranking = user_api.rate_user(owner)
    return ranking


# endregion

# region Leaderboards
@gentrys_quest_api_blueprint.route("/gq/get-top-players", methods=["GET"])
@require_scopes(["leaderboard:read"])
def top_players():
    start = request.args.get("start")
    amount = request.args.get("amount")
    online = request.args.get("online")
    return leaderboard_api.get_top_players(start=start, amount=amount, online=online == 'true')


@gentrys_quest_api_blueprint.route("/gq/get-leaderboard/<id>", methods=["GET"])
@require_scopes(["leaderboard:read"])
def get_leaderboard():
    return leaderboard_api.get_leaderboard(id)


@gentrys_quest_api_blueprint.route("/gq/submit-leaderboard", methods=['POST'])
@require_scopes(["leaderboard:write"])
def submit_leaderboard():
    leaderboard_id = int(request.form.get("leaderboard_id"))
    user = int(request.form.get("user"))
    score = int(request.form.get("score"))
    return leaderboard_api.submit_leaderboard(leaderboard_id, user, score)
# endregion
