# packages
import logging
import os
import time

# flask packages
from flask import Flask, g, request
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_bcrypt import Bcrypt
from werkzeug.middleware.proxy_fix import ProxyFix

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
from routes.api.payment_api_routes import payments_api_blueprint
from routes.api.status_api_routes import status_api_blueprint
#   pages
from routes.pages.main_routes import main_blueprint
from routes.pages.gentrys_quest_routes import gentrys_quest_blueprint
from routes.pages.account_routes import account_blueprint
from routes.pages.osu_routes import osu_blueprint

# apis and objects
from api.key_api import verify_api_key_header
from objects import Account


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

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
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

    # set up events
    @app.before_request
    def before_request():
        g.req_start = time.perf_counter()

    @app.after_request
    def after_request(response):
        g.req_duration = time.perf_counter() - g.req_start
        g.req_endpoint = request.path
        user_id = Account.id_from_session(request.cookies.get("session"))

        if user_id is None:
            api_key = request.headers.get("X-API-Key") or request.headers.get("Authorization")
            if api_key:
                key_user = verify_api_key_header()
                if key_user:
                    user_id = key_user

        ip_address = request.remote_addr
        success = 200 <= response.status_code < 500

        environment.database.execute(
            """
            INSERT INTO requests (endpoint, duration, \"user\", ip, successful)
            VALUES (%s, %s, %s, %s, %s)
            """,
            params=(
                g.req_endpoint,
                g.req_duration,
                user_id,
                ip_address,
                success
            )
        )
        return response

    # load blueprints
    #   api
    app.register_blueprint(key_blueprint, url_prefix='/auth')
    app.register_blueprint(account_api_blueprint, url_prefix='/api')
    app.register_blueprint(osu_api_blueprint, url_prefix='/api')
    app.register_blueprint(gentrys_quest_api_blueprint, url_prefix='/api')
    app.register_blueprint(payments_api_blueprint, url_prefix='/payment')
    app.register_blueprint(status_api_blueprint, url_prefix='/api')
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
