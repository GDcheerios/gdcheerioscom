# packages
import asyncio
import atexit
import json
import logging
import random
import string
import urllib

# flask packages
import requests
from flask import Flask, redirect, render_template, request, make_response
from flask_bcrypt import Bcrypt
from flask_socketio import SocketIO, emit

# credential variables
import Client_Credentials as client
from crap.Account import Account
# scripts
from crap.Initialization import *
from crap.PSQLConnection import PSQLConnection as DB

initialize_files()  # setup necessary files

# data imports
from crap.osu_crap.Match import Match
from crap.osu_crap.PlayerList import PlayerList
from crap.osu_crap.MatchHandler import MatchHandler

from crap.gentrys_quest_crap.GQManager import GQManager

# global vars
#   database
DB.connect()

#   osu data
live_player_status = {}
player_data = PlayerList
print("\nLoading osu players\n")
print("\nNo players available\n")

match_handler = MatchHandler()

#   Gentrys Quest data
GQManager.load_rankings()

# flask set up
app = Flask(  # Create a flask app
    __name__,
    template_folder='templates',  # Name of html file folder
    static_folder='static',  # Name of directory for static files
)
app.config['SECRET_KEY'] = Client_Credentials.secret
socketio = SocketIO(app, logger=False)
bcrypt = Bcrypt(app)

# logging config
log = logging.getLogger('werkzeug')
log.setLevel(logging.NOTSET)


# <editor-fold desc="API">

# <editor-fold desc="token API">
@app.route("/api/generate-token")
async def generate_token():
    token = ""
    for i in range(32):
        token += random.choice(string.ascii_letters)

    DB.do("INSERT INTO tokens values (%s);", params=(token,))
    return token


@app.route("/api/clear-tokens")
async def clear_tokens():
    DB.do("DELETE FROM tokens *;")
    return "Done"


@app.route("/api/delete-token/<token>")
async def delete_token(token):
    DB.do("DELETE FROM tokens WHERE value = %s;", params=(token,))
    return f"removed {token}"


@app.route("/api/verify-token/<token>")
def verify_token(token):
    return str(len(DB.get("SELECT %s FROM tokens;", params=(token,))) > 0)


# </editor-fold>

# <editor-fold desc="account API">
@app.route("/api/account/create/<email>+<username>+<password>")
async def account_create(username, password, email, osu_id=0, about_me=""):
    password = str(password)
    password = str(bcrypt.generate_password_hash(password))[2:-1]

    Account.create(username, password, email, osu_id, about_me)


def login(username, password) -> str | dict:
    account = Account(username)
    if account:
        if bcrypt.check_password_hash(account.password, password):
            return account.jsonify()

    return "incorrect info"


@app.route('/api/account/login-form', methods=['POST'])
async def login_cookie():
    username = request.form.get('nm')
    password = request.form.get('pw')
    login_result = login(username, password)
    if login_result != "incorrect info" and login_result is not None:
        resp = make_response(redirect(f'/user/{login_result["id"]}'))
        resp.set_cookie('userID', str(login_result["id"]))
        return resp
    else:
        resp = make_response(
            render_template('account/login.html', warning="incorrect info"))
        return resp


@app.route("/api/account/login-json", methods=['POST'])
async def login_json():
    username = request.json["username"]
    password = request.json["password"]

    login_result = login(username, password)
    if login_result != "incorrect info" and login_result is not None:
        return login_result


@app.route("/account/signout")
async def signout():
    resp = make_response(render_template('account/login.html'))
    resp.delete_cookie('userID')
    return resp


@app.route("/create-account", methods=['POST'])
def create_account():
    username = request.form.get("nm")
    if Account.name_exists(username):
        return redirect("/account/create")

    password = request.form.get("pw")
    email = request.form.get("em")
    try:
        osuid = int(request.form.get("id"))
    except:
        osuid = 0
    about_me = request.form.get("am")
    asyncio.run(account_create(username, password, email, osuid, about_me))
    login_result = login(username, password)
    if login_result != "incorrect info" and login_result is not None:
        resp = make_response(
            render_template('account/user-profile.html',
                            account=login_result
                            ))
        resp.set_cookie('userID', str(login_result["id"]))
        return resp
    else:
        resp = make_response(
            render_template('account/login.html', warning="incorrect info"))
        return resp


@app.route("/api/account/change-pfp", methods=["POST"])
def change_profile_picture():
    id = request.cookies.get('userID')
    account_data = Account(id)
    account_data.pfp = request.form.get("url")
    return render_template('account/user-profile.html',
                           account=account_data
                           )


@app.route("/api/account/change-username", methods=["POST"])
async def change_username():
    id = request.cookies.get("userID")
    account = Account(id)
    username = request.form.get("username")
    if not Account.name_exists(username):
        Account.change_username(int(id), username)

    return redirect(f'/user/{account.id}')


@app.route("/api/account/grab/<idname>")
async def grab_account(idname):
    return Account(idname).jsonify()


# </editor-fold>

# <editor-fold desc="osu API">
# osu auth stuff
@app.route('/code_grab')
def code_grab():
    code = urllib.parse.parse_qs(request.query_string.decode('utf-8'))["code"][0]

    response = requests.post("https://osu.ppy.sh/oauth/token",
                             json={'client_id': client.osu_client_id,
                                   'code': code,
                                   'client_secret': client.osu_secret,
                                   'grant_type': 'authorization_code',
                                   'redirect_uri': f"{client.domain}/code_grab",
                                   'scope': 'public'},
                             headers={'Accept': 'application/json',
                                      'Content-Type': 'application/json'})

    response = response.json()

    user_info = requests.get("https://osu.ppy.sh/api/v2/me/osu", headers={
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': f"Bearer {response['access_token']}"
    }).json()

    info = {
        "username": user_info["username"],
        "id": user_info["id"],
        "avatar": f"https://a.ppy.sh/{user_info['id']}",
        "background url": user_info["cover_url"]
    }

    return redirect(f"/account/create?osu_info={json.dumps(info)}")


# <editor-fold desc="match API">
@app.route("/api/get_match/<match_name>")
async def grabber(match_name, from_socket: bool = False):
    match = match_handler.get_match(match_name)

    new_dict = {}
    for player in match.players:
        new_dict[player.id] = {
            "background url": player.background,
            "score": match.get_score(player),
            "rank": player.rank,
            "playcount": match.get_playcount(player),
            "liveStatus": None if player.id not in live_player_status else live_player_status[player.id],
        }

    for team in match.team_data:
        for player_ref in team.players:
            new_dict[player_ref.id]["team"] = f"{team.jsonify()}"

    return new_dict


# </editor-fold>

# <editor-fold desc="player API">

@app.route("/refresh/<player_id>", methods=['GET', 'POST'])
async def web_player_refresh(player_id):
    player = PlayerList.get_users([player_id])[0]
    player.update_data()
    return player.jsonify()


@app.route("/api/grab/<ids>", methods=['GET'])
async def all_grabber(ids):
    id_list = ids.split("+")

    data = PlayerList.get_users(id_list)
    player_list = []
    for player in data:
        player_list.append(player.jsonify())

    return player_list


# </editor-fold>

# <editor-fold desc="live API">
@app.route("/api/live/del/<id>", methods=["POST"])
async def del_live_status(id):
    global live_player_status
    live_player_status.pop(int(id))


@app.route("/api/live/get/<id>", methods=["get"])
async def get_live_status(id):
    player_status = live_player_status[id]
    return player_status


@app.route("/api/live/get", methods=["get"])
async def get_all_live_status():
    return live_player_status


@app.route("/api/live/update/<id>", methods=["POST"])
async def update_live_status(id):
    global live_player_status
    info = request.json
    live_player_status[id] = info


# </editor-fold>

# </editor-fold>

# <editor-fold desc="gentrys quest API">

# <editor-fold desc="modern">

# <editor-fold desc="leaderboards">

@app.route("/api/gq/get-leaderboard/<id>")
async def gq_get_leaderboard(id):
    leaderboard = DB.get_group(
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


@app.route("/api/gq/submit-leaderboard/<leaderboard>/<user>+<score>", methods=['POST'])
async def gq_submit_leaderboard(leaderboard, user, score):
    user = Account(user)
    if DB.get("select online from leaderboards where id = %s", params=leaderboard)[0]:
        DB.do("INSERT INTO leaderboard_scores (name, score, leaderboard, \"user\") values (%s, %s, %s, %s);",
              params=(user.username, int(score), int(leaderboard), user.id))

    return {
        "username": user.username,
        "score": score
    }


# </editor-fold>

# </editor-fold>

# <editor-fold desc="classic">

# <editor-fold desc="leaderboards">

@app.route("/api/gqc/get-leaderboard/<start>+<display_number>", methods=["GET"])
async def get_gq_leaderboard(start, display_number):
    return GQManager.get_leaderboard(True, int(start), int(display_number))


# </editor-fold>

# </editor-fold>

# </editor-fold>

# </editor-fold>

# <editor-fold desc="templates">

# <editor-fold desc="main">

@app.route('/')
async def home():
    return render_template("index.html")


@app.route('/about')
async def about():
    return render_template("about.html")


@app.route("/down")
async def down():
    return render_template("down.html")


@app.route("/control")
async def web_control():
    return render_template(
        "control.html",
    )


# </editor-fold>

# <editor-fold desc="gentrys quest">

@app.route("/gentrys-quest")
async def gentrys_quest_home():
    return render_template("gentrys quest/home.html")


@app.route("/gentrys-quest/leaderboard")
async def gentrys_quest_leaderboard():
    players = GQManager.get_leaderboard(True)

    return render_template(
        "gentrys quest/leaderboard.html",
        players=players
    )


@app.route("/gentrys-quest/online-players")
async def gentrys_quest_online_players():
    players = GQManager.online_players

    def sort_thing(player):
        return player.power_level.weighted

    players.sort(key=sort_thing, reverse=True)

    return render_template(
        "gentrys quest/online-players.html",
        players=players,
        version=GQManager.rater_version
    )


@app.route("/gentrys-quest/ranking")
async def gentrys_quest_ranking():
    return render_template(
        "gentrys quest/ranking.html",
        ranking_info=GQManager.rater.get_tiers(),
        colors=GQManager.rater.rating_colors,
        gqc_id=GQManager.get_player,
        gqc_rank=GQManager.get_ranking
    )


# </editor-fold>

# <editor-fold desc="osu">

@app.route('/osu')
async def osu_home():
    return render_template("osu/index.html")


@app.route("/osu/matches/<match_name>")
def load_match(match_name):
    players = {}
    teams = {}

    match: Match = match_handler.get_match(match_name)

    for player in match.players:
        players[player.name] = [
            player.avatar,
            player.background,
            player.link,
            player.id,
            player.accuracy,
        ]

    for team in match.team_data:
        teams[team.team_name] = team.jsonify()

    return render_template(
        'osu/Current.html',
        players=players,
        match=match,
        nicknames=match.nicknames,
        teams=teams,
        live_status=live_player_status,
        get_osu_id=get_osu_id
    )


@app.route("/osu/matches")
async def matches_page():
    return render_template(
        'osu/matches.html',
        matches=match_handler
    )


# </editor-fold>

# <editor-fold desc="account">
@app.route("/user/<id>")
async def load_profile(id):
    account_info = Account(int(id))
    return render_template(
        "account/user-profile.html",
        account=account_info
    )


@app.route("/account/login")
async def login_page():
    return render_template("account/login.html")


@app.route("/account")
async def account_home():
    return render_template("account/create-one.html")


@app.route("/account/create")
async def account_create_page():
    osu_info = request.args.get("osu_info")
    if osu_info is not None:
        osu_info = json.loads(osu_info)
    return render_template("account/create.html",
                           client_id=client.osu_client_id,
                           redirect_uri=f"{client.domain}/code_grab",
                           osu_info=osu_info
                           )


# </editor-fold>


# </editor-fold>

# <editor-fold desc="helper methods">
def get_osu_id(userID):
    return json.load(open(f"accounts/{userID}.json",
                          "r"))["metadata"]["osu id"]


# </editor-fold>

# <editor-fold desc="sockets">
@socketio.on('event')
def test_socket(data):
    print(data)


@socketio.on('update client status')
def update_client_status(data):
    print("updating", data["user"])
    live_player_status[data["user"]] = data


@socketio.on('match data get')
def get_livestatus(data):
    emit('match data receive', asyncio.run(grabber(data, True)))


# </editor-fold>


if __name__ == "__main__":
    server_port = os.environ.get('PORT', client.port)

    socketio.run(
        app,
        host='0.0.0.0',
        port=server_port,
        allow_unsafe_werkzeug=True,
        debug=client.debug
    )
