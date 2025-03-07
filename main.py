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
        template_folder='templates',  # Name of html file folder
        static_folder='static',  # Name of directory for static files
    )

    @app.context_processor
    def inject_variables():
        return {'rater': environment.rater}

    app.config['SECRET_KEY'] = environment.secret
    environment.bcrypt = Bcrypt(app)

    # logging config
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.NOTSET)

    # load blueprints
    #   api
    app.register_blueprint(token_blueprint, url_prefix='/api')
    app.register_blueprint(account_api_blueprint, url_prefix='/api')
    app.register_blueprint(osu_api_blueprint, url_prefix='/api')
    app.register_blueprint(gentrys_quest_api_blueprint, url_prefix='/api')

    #   pages
    app.register_blueprint(main_blueprint)
    app.register_blueprint(gentrys_quest_blueprint, url_prefix='/gentrys-quest')
    app.register_blueprint(account_blueprint, url_prefix='/account')

    return app


def json_to_html(data):
    html_string = "<table border='1'>"

    # Function to handle nested objects and lists
    def render_row(key, value):
        # If the value is a dictionary, render a nested table
        if isinstance(value, dict):
            return f"<tr><td>{key}</td><td>{json_to_html(value)}</td></tr>"
        # If the value is a list, render each item in the list
        elif isinstance(value, list):
            items = "".join(
                [f"<li>{json_to_html(item) if isinstance(item, (dict, list)) else item}</li>" for item in value])
            return f"<tr><td>{key}</td><td><ul>{items}</ul></td></tr>"
        else:
            # Render the key-value pair in a table row
            return f"<tr><td>{key}</td><td>{value}</td></tr>"

    # Iterate through the JSON object and convert to HTML
    for key, value in data.items():
        html_string += render_row(key, value)

    html_string += "</table>"
    return html_string


def get_token(auth):
    token = auth.get("Authorization")
    if "Bearer" in token:
        return token[7:]

    return token


if __name__ == "__main__":
    server_port = os.environ.get('PORT', environment.port)

    create_app().run(
        host='0.0.0.0',
        port=server_port,
        debug=environment.debug
    )
