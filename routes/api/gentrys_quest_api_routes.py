import json

from flask import Blueprint, g, jsonify, request

import environment
from api.gentrys_quest import leaderboard_api, user_api
from api.key_api import require_scopes
from objects import Account

gentrys_quest_api_blueprint = Blueprint("gentrys_quest_api_blueprint", __name__)


def _enforce_user_scope(target_user_id: int | str):
    have_scopes = set(g.get("current_scopes", []))
    if "admin" in have_scopes:
        return None

    current_user_id = g.get("current_user_id")
    if str(current_user_id) != str(target_user_id):
        return jsonify({"error": "forbidden"}), 403

    return None


# region Users
@gentrys_quest_api_blueprint.get("/gq/get-items/<int:id>")
@require_scopes(["account:read"])
def get_items(id: int):
    denied = _enforce_user_scope(id)
    if denied:
        return denied
    return {"items": user_api.get_items(id)}


@gentrys_quest_api_blueprint.get("/gq/set-xp/<int:id>/<int:xp>")
@require_scopes(["account:write"])
def set_xp(id: int, xp: int):
    denied = _enforce_user_scope(id)
    if denied:
        return denied
    user_api.set_xp(id, xp)
    return user_api.get_xp(id)


@gentrys_quest_api_blueprint.get("/gq/get-xp/<int:id>")
@require_scopes(["account:read"])
def get_xp(id: int):
    denied = _enforce_user_scope(id)
    if denied:
        return denied
    return user_api.get_xp(id)


@gentrys_quest_api_blueprint.get("/gq/get/<int:id>")
@require_scopes(["account:read"])
def get(id: int):
    denied = _enforce_user_scope(id)
    if denied:
        return denied
    return Account(id).jsonify()["gq data"]


@gentrys_quest_api_blueprint.post("/gq/create/")
@require_scopes(["account:write"])
def gq_create():
    data = request.get_json(silent=True) or {}
    target_id = data.get("ID")
    if target_id is None:
        return jsonify({"error": "missing_ID"}), 400

    denied = _enforce_user_scope(target_id)
    if denied:
        return denied

    check = environment.database.fetch_one("SELECT id FROM gq_data WHERE id = %s", params=(target_id,))
    if check is None:
        environment.database.execute(
            "INSERT INTO gq_data (id, money, score) VALUES (%s, 0, 0)",
            params=(target_id,)
        )
        return "Success", 200

    return "User already exists", 400


@gentrys_quest_api_blueprint.post("/gq/add-item/")
@require_scopes(["account:write"])
def add_item():
    data = request.get_json(silent=True) or {}
    owner_id = data.get("owner")
    item_data = data.get("item")
    item_type = data.get("type")
    if owner_id is None or item_data is None or item_type is None:
        return jsonify({"error": "invalid_payload"}), 400

    denied = _enforce_user_scope(owner_id)
    if denied:
        return denied

    metadata_json = json.dumps(item_data)
    rating = environment.gq_rater.get_rating(item_type, item_data)
    created_item = environment.database.fetch_to_dict(
        """
        INSERT INTO gq_items (type, metadata, owner, rating)
        VALUES (%s, %s::jsonb, %s, %s)
        RETURNING *
        """,
        params=(item_type, metadata_json, owner_id, rating)
    )
    created_item["metadata"]["ID"] = created_item["id"]
    environment.database.execute(
        """
        UPDATE gq_items
        SET metadata = %s::jsonb
        WHERE id = %s
        """,
        params=(json.dumps(created_item["metadata"]), created_item["id"])
    )
    ranking = user_api.rate_user(owner_id)
    return {
        "ranking": ranking,
        "item": created_item
    }


@gentrys_quest_api_blueprint.post("/gq/update-item/")
@require_scopes(["account:write"])
def update_item():
    data = request.get_json(silent=True) or {}
    item = data.get("item") or {}
    item_id = item.get("ID")
    item_type = data.get("type")
    if item_id is None or item_type is None:
        return jsonify({"error": "invalid_payload"}), 400

    owner = environment.database.fetch_one("SELECT owner FROM gq_items WHERE id = %s", params=(item_id,))
    if not owner:
        return jsonify({"error": "item_not_found"}), 404

    denied = _enforce_user_scope(owner[0])
    if denied:
        return denied

    metadata_json = json.dumps(item)
    rating = environment.gq_rater.get_rating(item_type, item)
    updated_item = environment.database.fetch_to_dict(
        """
        UPDATE gq_items
        SET metadata = %s::jsonb,
            rating   = %s
        WHERE id = %s
        RETURNING *
        """,
        params=(metadata_json, rating, item_id)
    )
    ranking = user_api.rate_user(updated_item["owner"])
    return {
        "ranking": ranking,
        "item": updated_item
    }


@gentrys_quest_api_blueprint.post("/gq/remove-item/<int:id>")
@require_scopes(["account:write"])
def remove_item(id: int):
    owner = environment.database.fetch_one("SELECT owner FROM gq_items WHERE id = %s", params=(id,))
    if not owner:
        return jsonify({"error": "item_not_found"}), 404

    owner = owner[0]
    denied = _enforce_user_scope(owner)
    if denied:
        return denied

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
    return leaderboard_api.get_top_players(start=start, amount=amount, online=online == "true")


@gentrys_quest_api_blueprint.route("/gq/get-leaderboard/<int:id>", methods=["GET"])
@require_scopes(["leaderboard:read"])
def get_leaderboard(id: int):
    return leaderboard_api.get_leaderboard(id)


@gentrys_quest_api_blueprint.route("/gq/submit-leaderboard", methods=["POST"])
@require_scopes(["leaderboard:write"])
def submit_leaderboard():
    try:
        leaderboard_id = int(request.form.get("leaderboard_id"))
        user = int(request.form.get("user"))
        score = int(request.form.get("score"))
    except (TypeError, ValueError):
        return jsonify({"error": "invalid_payload"}), 400

    denied = _enforce_user_scope(user)
    if denied:
        return denied

    return leaderboard_api.submit_leaderboard(leaderboard_id, user, score)
# endregion
