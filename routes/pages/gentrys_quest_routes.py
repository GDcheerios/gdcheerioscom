from flask import Blueprint, render_template, redirect, request

import environment
from api.gentrys_quest.leaderboard_api import get_top_players, get_leaderboard
from objects import Account

gentrys_quest_blueprint = Blueprint("gentrys_quest_blueprint", __name__)


# inject variables into templates
@gentrys_quest_blueprint.context_processor
def inject_version(): return {
    "gq_version": environment.gq_version,
    "rater": environment.gq_rater,
    "get_top_players": get_top_players,
    "get_leaderboard": get_leaderboard
}


@gentrys_quest_blueprint.route("/")
def gentrys_quest_home(): return render_template("gentrys quest/home.html")


@gentrys_quest_blueprint.route("/leaderboard")
def gentrys_quest_leaderboard():
    players = get_top_players(amount=5)
    user_id = Account.id_from_session(request.cookies.get("session"))
    if user_id:
        user_id = int(user_id)

        found_you = False
        for player in players:
            player["you"] = int(player.get("id", 0)) == user_id
            if player["you"]:
                found_you = True

        if not found_you:
            user_account = Account(user_id)
            user_ranking = user_account.gq_data.get("ranking")
            if user_ranking:
                players.append({
                    "placement": user_ranking.get("placement"),
                    "id": user_id,
                    "username": user_account.username,
                    "weighted": user_ranking.get("weighted"),
                    "rank": user_ranking.get("rank"),
                    "tier": user_ranking.get("tier"),
                    "you": True,
                })
    else:
        for player in players:
            player["you"] = False

    event_leaderboard = get_leaderboard(3, amount=5, user_id=user_id)
    if event_leaderboard:
        event_rows = event_leaderboard.get("leaderboard") or []
        found_you = False

        for player in event_rows:
            player_id = player.get("id")
            player["you"] = bool(user_id) and player_id is not None and int(player_id) == user_id
            if player["you"]:
                found_you = True

        if user_id and event_leaderboard.get("user_placement") and not found_you:
            event_rows.append({
                "placement": event_leaderboard["user_placement"].get("placement"),
                "id": event_leaderboard["user_placement"].get("id"),
                "username": event_leaderboard["user_placement"].get("username"),
                "score": event_leaderboard["user_placement"].get("score"),
                "weighted": event_leaderboard["user_placement"].get("weighted"),
                "rank": event_leaderboard["user_placement"].get("rank"),
                "tier": event_leaderboard["user_placement"].get("tier"),
                "you": True,
            })

        event_leaderboard["leaderboard"] = event_rows

    return render_template(
        "gentrys quest/leaderboard.html",
        players=players,
        event_leaderboard=event_leaderboard
    )


@gentrys_quest_blueprint.route("/levels")
def gentrys_quest_levels(): return render_template(
    "gentrys quest/levels.html",
    levels=environment.gq_levels,
    level_colors=environment.gq_level_colors
)


@gentrys_quest_blueprint.route("/ranking")
def gentrys_quest_ranking():
    global user_ranking
    user_id = Account.id_from_session(request.cookies.get("session"))
    if user_id:
        user_ranking = Account(user_id).gq_data["ranking"]
    return render_template("gentrys quest/ranking.html", user_ranking=user_ranking)
