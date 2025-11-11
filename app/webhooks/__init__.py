from flask import Blueprint

webhooks_bp = Blueprint("webhooks", __name__, url_prefix="/stripe")

from . import routes  # noqa
