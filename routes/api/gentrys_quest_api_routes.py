from flask import Blueprint

from api.gentrys_quest import leaderboard_api
from environment import database
from objects import Account

gentrys_quest_api_blueprint = Blueprint("gentrys_quest_api_blueprint", __name__)


# region Main
@gentrys_quest_api_blueprint.route("/gq/get-version", methods=["GET"])
def version(): return ""  # todo: implement this functionality


# endregion

# region Leaderboards
@gentrys_quest_api_blueprint.route("/gq/get-leaderboard/<start>+<amount>+<online>", methods=["GET"])
def leaderboard(start, amount, online): return leaderboard_api.leaderboard(start, amount, online=online == 'true')


@gentrys_quest_api_blueprint.route("gq/get-ig-leaderboard/<id>", methods=["GET"])
async def gq_get_leaderboard(id): return leaderboard_api.in_game_leaderboard(id)


@gentrys_quest_api_blueprint.route("/gq/submit-leaderboard/<leaderboard>/<user>+<score>", methods=['POST'])
async def gq_submit_leaderboard(leaderboard_id, user, score): return leaderboard_api.submit_leaderboard(leaderboard_id, user, score)
# endregion


