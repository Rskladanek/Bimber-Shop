from flask import Blueprint

shop_bp = Blueprint("shop", __name__, template_folder="templates")

from .routes import shop_bp  # noqa
