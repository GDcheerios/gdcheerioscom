# packages
import logging
import os

# flask packages
from flask import Flask
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_bcrypt import Bcrypt

# environment
import environment

# util
from utils import bucket_helper as bucket

# routes
#   api
from routes.api.key_routes import key_blueprint
from routes.api.account_api_routes import account_api_blueprint
from routes.api.osu_api_routes import osu_api_blueprint
from routes.api.gentrys_quest_api_routes import gentrys_quest_api_blueprint

#   pages
from routes.pages.main_routes import main_blueprint
from routes.pages.gentrys_quest_routes import gentrys_quest_blueprint
from routes.pages.account_routes import account_blueprint
from routes.pages.osu_routes import osu_blueprint


def match_room(match_id: str) -> str:
    return f"match:{match_id}"


def register_socket_handlers(socketio):
    @socketio.on("join_match")
    def on_join_match(data):
        match_id = str((data or {}).get("match_id", "")).strip()
        if not match_id:
            emit("error", {"message": "match_id is required"})
            return

        join_room(match_room(match_id))
        emit("joined_match", {"match_id": match_id})

    @socketio.on("leave_match")
    def on_leave_match(data):
        match_id = str((data or {}).get("match_id", "")).strip()
        if not match_id:
            return
        leave_room(match_room(match_id))
        emit("left_match", {"match_id": match_id})


def create_app():
    app = Flask(  # Create a flask app
        __name__,
        template_folder='templates',  # Name of HTML file folder
        static_folder='static',  # Name of directory for static files
    )

    app.config['SECRET_KEY'] = environment.secret
    environment.bcrypt = Bcrypt(app)

    @app.context_processor
    def inject_template_vars():
        return {
            "bucket": bucket
        }

    # logging config
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.NOTSET)

    # load blueprints
    #   api
    app.register_blueprint(key_blueprint, url_prefix='/auth')
    app.register_blueprint(account_api_blueprint, url_prefix='/api')
    app.register_blueprint(osu_api_blueprint, url_prefix='/api')
    app.register_blueprint(gentrys_quest_api_blueprint, url_prefix='/api')

    #   pages
    app.register_blueprint(main_blueprint)
    app.register_blueprint(gentrys_quest_blueprint, url_prefix='/gentrys-quest')
    app.register_blueprint(account_blueprint, url_prefix='/account')
    app.register_blueprint(osu_blueprint, url_prefix='/osu')

    return app


if __name__ == "__main__":
    server_port = os.environ.get('PORT', environment.port)
    
    app = create_app()
    socketio = SocketIO(app)
    register_socket_handlers(socketio)
    environment.socket = socketio
    socketio.run(app, host='0.0.0.0', port=server_port, debug=environment.debug, allow_unsafe_werkzeug=True)
