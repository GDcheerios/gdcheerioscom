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


@gentrys_quest_api_blueprint.get("/gq/get-ranking/<id>")
@require_scopes(["account:read"])
def get_ranking(id: int):
    return user_api.get_ranking(id)


@gentrys_quest_api_blueprint.post("/gq/visit/")
@require_scopes(["account:write"])
def visit():
    return environment.database.fetch_to_dict(
        """
        INSERT INTO gq_visitations (user_id,
                                    location)
        VALUES (%s, %s)
        RETURNING *
        """,
        params=(
            request.json.get("user_id"),
            request.json.get("location")
        )
    )


@gentrys_quest_api_blueprint.post("/gq/depart/<id>")
@require_scopes(["account:write"])
def depart(id: str):
    environment.database.fetch_to_dict(
        """
        UPDATE gq_visitations
        SET departed = NOW()
        WHERE id = %s
        """,
        params=(id,)
    )

    return "Success"


# endregion

# region Leaderboards
@gentrys_quest_api_blueprint.route("/gq/get-top-players", methods=["GET"])
@require_scopes(["leaderboard:read"])
def top_players():
    start = request.args.get("start", 0, type=int)
    amount = request.args.get("amount", 10, type=int)
    online = request.args.get("online", "false")
    return leaderboard_api.get_top_players(start=start, amount=amount, online=online == "true")


@gentrys_quest_api_blueprint.route("/gq/get-leaderboard/<int:id>", methods=["GET"])
@require_scopes(["leaderboard:read"])
def get_leaderboard(id: int):
    amount = int(request.args.get('amount', 0))
    user_id: str | None = request.args.get('user_id', None)
    standings = leaderboard_api.get_leaderboard(id, amount, user_id)
    return standings


@gentrys_quest_api_blueprint.get("/gq/get-leaderboard-placement/<int:id>")
@require_scopes(["leaderboard:read"])
def get_placement(id: int):
    user_id = request.args.get(
        "user",
        Account.id_from_session(request.cookies.get('session'))
    )

    result = leaderboard_api.get_placement(id, user_id)
    return result if result else {"error": 404, "message": "No user placement found"}


@gentrys_quest_api_blueprint.get("/gq/get-statistics")
@require_scopes(["leaderboard:read"])
def get_statistics():
    leaderboard_id = request.args.get("leaderboard_id", type=int)

    raw_user_id = request.args.get("user_id")
    if raw_user_id is None:
        target_user_id = g.get("current_user_id")
    else:
        try:
            target_user_id = int(raw_user_id)
        except (TypeError, ValueError):
            return jsonify({"error": "invalid_user_id"}), 400

    denied = _enforce_user_scope(target_user_id)
    if denied:
        return denied

    score_overview = environment.database.fetch_to_dict(
        """
        SELECT COUNT(DISTINCT "user")::bigint  AS total_players,
               COUNT(*)::bigint                AS total_plays,
               COALESCE(SUM(score), 0)::bigint AS total_score,
               AVG(score)::float               AS average_score
        FROM gq_scores
        WHERE (%s IS NULL OR leaderboard = %s)
        """,
        params=(leaderboard_id, leaderboard_id)
    ) or {}

    leaderboard_statistics = environment.database.fetch_to_dict(
        """
        SELECT COALESCE(SUM(amount), 0)::bigint AS total_amount,
               AVG(amount)::float               AS average_amount
        FROM gq_statistics
        WHERE (%s IS NULL OR leaderboard = %s)
        """,
        params=(leaderboard_id, leaderboard_id)
    ) or {}

    leaderboard_statistics_by_type = environment.database.fetch_all_to_dict(
        """
        SELECT "type",
               COALESCE(SUM(amount), 0)::bigint AS total_amount,
               AVG(amount)::float               AS average_amount
        FROM gq_statistics
        WHERE (%s IS NULL OR leaderboard = %s)
        GROUP BY "type"
        ORDER BY "type"
        """,
        params=(leaderboard_id, leaderboard_id)
    ) or []

    user_score_overview = environment.database.fetch_to_dict(
        """
        SELECT COUNT(*)::bigint                 AS total_plays,
               COALESCE(SUM(score), 0)::bigint AS total_score,
               AVG(score)::float               AS average_score
        FROM gq_scores
        WHERE "user" = %s
          AND (%s IS NULL OR leaderboard = %s)
        """,
        params=(target_user_id, leaderboard_id, leaderboard_id)
    ) or {}

    user_statistics = environment.database.fetch_to_dict(
        """
        SELECT COALESCE(SUM(amount), 0)::bigint AS total_amount,
               AVG(amount)::float               AS average_amount
        FROM gq_statistics
        WHERE "user" = %s
          AND (%s IS NULL OR leaderboard = %s)
        """,
        params=(target_user_id, leaderboard_id, leaderboard_id)
    ) or {}

    user_statistics_by_type = environment.database.fetch_all_to_dict(
        """
        SELECT "type",
               COALESCE(SUM(amount), 0)::bigint AS total_amount,
               AVG(amount)::float               AS average_amount
        FROM gq_statistics
        WHERE "user" = %s
          AND (%s IS NULL OR leaderboard = %s)
        GROUP BY "type"
        ORDER BY "type"
        """,
        params=(target_user_id, leaderboard_id, leaderboard_id)
    ) or []

    last_run_row = environment.database.fetch_to_dict(
        """
        SELECT visitation, score
        FROM gq_scores
        WHERE "user" = %s
          AND (%s IS NULL OR leaderboard = %s)
          AND visitation IS NOT NULL
        ORDER BY id DESC
        LIMIT 1
        """,
        params=(target_user_id, leaderboard_id, leaderboard_id)
    ) or {}

    last_run = None
    visitation = last_run_row.get("visitation")

    if visitation:
        last_run_stats = environment.database.fetch_to_dict(
            """
            SELECT COALESCE(SUM(amount), 0)::bigint AS total_amount,
                   AVG(amount)::float               AS average_amount
            FROM gq_statistics
            WHERE "user" = %s
              AND visitation = %s
              AND (%s IS NULL OR leaderboard = %s)
            """,
            params=(target_user_id, visitation, leaderboard_id, leaderboard_id)
        ) or {}

        last_run_stats_by_type = environment.database.fetch_all_to_dict(
            """
            SELECT "type",
                   COALESCE(SUM(amount), 0)::bigint AS total_amount,
                   AVG(amount)::float               AS average_amount
            FROM gq_statistics
            WHERE "user" = %s
              AND visitation = %s
              AND (%s IS NULL OR leaderboard = %s)
            GROUP BY "type"
            ORDER BY "type"
            """,
            params=(target_user_id, visitation, leaderboard_id, leaderboard_id)
        ) or []

        last_run = {
            "visitation": visitation,
            "score": last_run_row.get("score"),
            "statistics": {
                "total_amount": last_run_stats.get("total_amount") or 0,
                "average_amount": last_run_stats.get("average_amount"),
                "by_type": last_run_stats_by_type,
            },
        }

    return {
        "leaderboard_id": leaderboard_id,
        "leaderboard": {
            "total_players": score_overview.get("total_players") or 0,
            "total_plays": score_overview.get("total_plays") or 0,
            "total_score": score_overview.get("total_score") or 0,
            "average_score": score_overview.get("average_score"),
            "statistics": {
                "total_amount": leaderboard_statistics.get("total_amount") or 0,
                "average_amount": leaderboard_statistics.get("average_amount"),
                "by_type": leaderboard_statistics_by_type,
            },
        },
        "user": {
            "id": int(target_user_id),
            "scores": {
                "total_plays": user_score_overview.get("total_plays") or 0,
                "total_score": user_score_overview.get("total_score") or 0,
                "average_score": user_score_overview.get("average_score"),
            },
            "statistics": {
                "total_amount": user_statistics.get("total_amount") or 0,
                "average_amount": user_statistics.get("average_amount"),
                "by_type": user_statistics_by_type,
            },
            "last_run": last_run,
        },
    }


@gentrys_quest_api_blueprint.route("/gq/submit-leaderboard", methods=["POST"])
@require_scopes(["leaderboard:write"])
def submit_leaderboard():
    try:
        leaderboard_id = int(request.json.get("leaderboard_id"))
        user = int(request.json.get("user"))
        score = int(request.json.get("score"))
        visitation = request.json.get("visitation")
    except (TypeError, ValueError):
        print(request.json)
        return jsonify({"error": "invalid_payload"}), 400

    denied = _enforce_user_scope(user)
    if denied:
        return denied

    return leaderboard_api.submit_leaderboard(leaderboard_id, user, score, visitation)
# endregion
