from flask import Blueprint, request

import environment
from api.gentrys_quest import leaderboard_api, user_api
from api.token_api import verify_token
from objects import Account
from environment import database
from utils.authentication import get_token

gentrys_quest_api_blueprint = Blueprint("gentrys_quest_api_blueprint", __name__)


# region Version
@gentrys_quest_api_blueprint.route("/gq/get-version", methods=["GET"])
def version(): return environment.gq_version


@gentrys_quest_api_blueprint.route("/gq/set-version", methods=["POST"])
def set_version():
    if environment.secret == request.form.get("secret"):
        database.execute(
            f"UPDATE server SET version = %s",
            params=(request.form.get("version"),)
        )


# endregion

# region Users
@gentrys_quest_api_blueprint.route("/gq/check-in/<id>", methods=["GET"])
def check_in(id: int):
    return user_api.check_in(id)


@gentrys_quest_api_blueprint.route("/gq/check-out/<id>", methods=["GET"])
def check_out(id: int): return user_api.check_out(id)


@gentrys_quest_api_blueprint.route("/gq/get-items/<id>", methods=["GET"])
def get_items(id: int): return {'items': user_api.get_items(id)}


@gentrys_quest_api_blueprint.route("gq/set-xp/<id>/<xp>", methods=["GET"])
def set_xp(id, xp):
    user_api.set_xp(int(id), int(xp))
    return user_api.get_xp(id)


@gentrys_quest_api_blueprint.route("gq/get-xp/<id>", methods=["GET"])
def get_xp(id): return user_api.get_xp(int(id))


@gentrys_quest_api_blueprint.route("/gq/get/<id>", methods=["GET"])
def get(id: int): return Account(id).jsonify()["gq data"]


@gentrys_quest_api_blueprint.route("/gq/save/", methods=["POST"])
def save():
    if verify_token(get_token(request.headers.get("Authorization"))):
        data = request.json
        if database.fetch_one("SELECT id FROM accounts WHERE id = %s", params=(data["id"],))[0] is not None:
            database.execute(
                "UPDATE gq_data SET money = %s, start_amount = %s, xp = %s WHERE id = %s",
                params=(
                    data["money"],
                    data["start_amount"],
                    data["xp"],
                    data["id"]
                )
            )
        else:
            database.execute(
                "INSERT INTO gq_data (id, xp, money, start_amount) VALUES (%s, 0, 0, 0)", params=(data["id"],)
            )

        return "Success", 200

    return "Failed", 401


# endregion

# region Leaderboards
@gentrys_quest_api_blueprint.route("/gq/get-leaderboard/<start>+<amount>+<online>", methods=["GET"])
def leaderboard(start, amount, online): return leaderboard_api.player_leaderboard(start, amount, online=online == 'true')


@gentrys_quest_api_blueprint.route("gq/get-ig-leaderboard/<id>", methods=["GET"])
def gq_get_leaderboard(id): return leaderboard_api.get_leaderboard(id)


@gentrys_quest_api_blueprint.route("/gq/submit-leaderboard/<leaderboard>/<user>+<score>", methods=['POST'])
def gq_submit_leaderboard(leaderboard_id, user, score): return leaderboard_api.submit_leaderboard(leaderboard_id,
                                                                                                  user, score)
# endregion
