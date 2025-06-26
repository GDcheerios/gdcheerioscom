from flask import Blueprint, request

from api import token_api

token_blueprint = Blueprint('token', __name__)


@token_blueprint.route('/token/generate', methods=['POST'])
def route_generate_token(): return token_api.generate_token()


@token_blueprint.route('/token/clear', methods=['POST'])
def route_clear_token(): return token_api.clear_tokens()


@token_blueprint.route("/token/delete", methods=["POST"])
def route_delete_token(): return token_api.delete_token(request.json["token"])


@token_blueprint.route("/token/verify", methods=["POST"])
def route_verify_token(): return token_api.verify_token(request.json["token"])
