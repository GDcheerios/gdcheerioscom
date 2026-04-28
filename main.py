# packages
import logging
import os
import time

# flask packages
from flask import Flask, g, request, render_template
from flask_bcrypt import Bcrypt
from werkzeug.middleware.proxy_fix import ProxyFix

# environment
import environment

# util
from utils.logger import (
    TaskTracker,
    build_request_payload,
    log_request,
    request_start,
    setup_logger,
)

# routes
#   api
from routes.api.key_routes import key_blueprint
from routes.api.oauth_api_routes import oauth_api_routes
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

server_logger = setup_logger("main")
startup_tracker = TaskTracker(server_logger, name="flask_server_startup")


def register_error_pages():
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('errors/500.html'), 500


def create_app():
    startup_tracker.start("app_creation")
    app = Flask(  # Create a flask app
        __name__,
        template_folder='templates',  # Name of HTML file folder
        static_folder='static',  # Name of directory for static files
    )
    startup_tracker.done("app_creation")

    startup_tracker.start("middleware_and_config")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    app.config['SECRET_KEY'] = environment.secret
    environment.bcrypt = Bcrypt(app)
    startup_tracker.done("middleware_and_config")

    startup_tracker.start("context_processor")

    @app.context_processor
    def inject_template_vars():
        return {}

    startup_tracker.done("context_processor")

    # logging config
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    logging.getLogger("flask.app").setLevel(logging.ERROR)

    # set up events
    startup_tracker.start("request_hooks")

    @app.before_request
    def before_request():
        request_start()

    @app.after_request
    def after_request(response):
        g.req_duration = time.perf_counter() - g.req_start
        g.req_endpoint = request.path
        static = True

        if not g.req_endpoint.startswith('/static'):
            user_id = Account.id_from_session(request.cookies.get("session"))
            static = False

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

        request_payload = build_request_payload(
            response_status=response.status_code,
            user_id=user_id if 'user_id' in locals() else None,
            successful=(200 <= response.status_code < 500),
        )
        if not static: log_request(server_logger, request_payload)

        return response

    startup_tracker.done("request_hooks")

    # load blueprints
    startup_tracker.start("blueprint_registration")
    #   api
    app.register_blueprint(key_blueprint, url_prefix='/auth')
    app.register_blueprint(oauth_api_routes, url_prefix='/oauth')
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
    startup_tracker.done("blueprint_registration")
    return app


app = create_app()
startup_tracker.start("error_pages_setup")
register_error_pages()
startup_tracker.done("error_pages_setup")
startup_tracker.warn_unfinished()
startup_tracker.complete()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=environment.debug,
    )
