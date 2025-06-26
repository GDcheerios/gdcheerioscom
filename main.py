# packages
import logging
import os

# flask packages
from flask import Flask
from flask_bcrypt import Bcrypt

# environment
import environment

# routes
#   api
from routes.api.token_routes import token_blueprint
from routes.api.account_api_routes import account_api_blueprint
from routes.api.osu_api_routes import osu_api_blueprint
from routes.api.gentrys_quest_api_routes import gentrys_quest_api_blueprint

#   pages
from routes.pages.main_routes import main_blueprint
from routes.pages.gentrys_quest_routes import gentrys_quest_blueprint
from routes.pages.account_routes import account_blueprint


def create_app():
    app = Flask(  # Create a flask app
        __name__,
        template_folder='templates',  # Name of HTML file folder
        static_folder='static',  # Name of directory for static files
    )

    @app.context_processor
    def inject_variables():
        return {'rater': environment.gq_rater}

    app.config['SECRET_KEY'] = environment.secret
    environment.bcrypt = Bcrypt(app)

    # logging config
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.NOTSET)

    # load blueprints
    #   api
    # app.register_blueprint(token_blueprint, url_prefix='/api')
    app.register_blueprint(account_api_blueprint, url_prefix='/api')
    app.register_blueprint(osu_api_blueprint, url_prefix='/api')
    # app.register_blueprint(gentrys_quest_api_blueprint, url_prefix='/api')

    #   pages
    app.register_blueprint(main_blueprint)
    # app.register_blueprint(gentrys_quest_blueprint, url_prefix='/gentrys-quest')
    app.register_blueprint(account_blueprint, url_prefix='/account')

    return app


if __name__ == "__main__":
    server_port = os.environ.get('PORT', environment.port)

    create_app().run(
        host='0.0.0.0',
        port=server_port,
        debug=environment.debug
    )
