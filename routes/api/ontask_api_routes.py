import environment

from utils.logger import setup_logger

from flask import Blueprint

ontask_api_blueprint = Blueprint('ontask_blueprint', __name__)
logger = setup_logger('routes.api.ontask')
