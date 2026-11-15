import environment

from utils.logger import setup_logger

from flask import Blueprint, render_template

ontask_blueprint = Blueprint('ontask', __name__)
logger = setup_logger('routes.ontask')


@ontask_blueprint.route('/')
def index():
    return render_template('ontask/index.html')
