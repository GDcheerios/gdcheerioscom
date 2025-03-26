from flask import Blueprint, request

import environment
from api.gentrys_quest import leaderboard_api, user_api
from objects import Account
from environment import database

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
def check_out(id: int):
    return user_api.check_out(id)

# endregion

# region Leaderboards
@gentrys_quest_api_blueprint.route("/gq/get-leaderboard/<start>+<amount>+<online>", methods=["GET"])
def leaderboard(start, amount, online): return leaderboard_api.leaderboard(start, amount, online=online == 'true')


@gentrys_quest_api_blueprint.route("gq/get-ig-leaderboard/<id>", methods=["GET"])
async def gq_get_leaderboard(id): return leaderboard_api.in_game_leaderboard(id)


@gentrys_quest_api_blueprint.route("/gq/submit-leaderboard/<leaderboard>/<user>+<score>", methods=['POST'])
async def gq_submit_leaderboard(leaderboard_id, user, score): return leaderboard_api.submit_leaderboard(leaderboard_id,
                                                                                                        user, score)
# endregion
