import environment

from flask import Blueprint

math_routes = Blueprint("math", __name__)


@math_routes.post("/create")
def math_create():



@math_routes.route("/host/<id>")
def math_host():
