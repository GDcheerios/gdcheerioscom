from flask import Blueprint, request

from api import account_api

account_blueprint = Blueprint('account', __name__)

@account_blueprint.route("/account/create/<email>+<username>+<password>")
