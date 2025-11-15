# app/__init__.py

from flask import Flask
from .config import Config
from .extensions import db, migrate, login_manager, oauth
from .cli import register_cli

# import modeli i blueprintów
from .models import User
from .auth import auth_bp
from .admin import admin_bp
from .blog import blog_bp
from .shop import shop_bp
from .webhooks import webhooks_bp


def create_app(config_class=Config) -> Flask:
    """Fabryka aplikacji Flask dla sklepu Bimberek."""

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    # --- Inicjalizacja rozszerzeń ---
    db.init_app(app)
    migrate.init_app(app, db)

    # --- Login manager ---
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id: str):
        return User.query.get(int(user_id))

    # --- OAuth (Authlib) ---
    oauth.init_app(app)
    # Rejestracja Google
    oauth.register(
        name="google",
        client_id=app.config.get("GOOGLE_CLIENT_ID"),
        client_secret=app.config.get("GOOGLE_CLIENT_SECRET"),
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
    
    # [ZMIANA] Rejestracja Facebook (Logowanie 5.0)
    oauth.register(
        name="facebook",
        client_id=app.config.get("FACEBOOK_CLIENT_ID"),
        client_secret=app.config.get("FACEBOOK_CLIENT_SECRET"),
        authorize_url="https://www.facebook.com/v10.0/dialog/oauth",
        access_token_url="https://graph.facebook.com/v10.0/oauth/access_token",
        # Używamy authorize_params, aby jawnie poprosić o email i profil
        authorize_params={"scope": "email,public_profile"},
        # Definiujemy endpoint API do pobrania danych użytkownika
        userinfo_endpoint="https://graph.facebook.com/me?fields=id,name,email",
        client_kwargs={"scope": "email public_profile"},
    )


    # --- Rejestracja blueprintów ---
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(blog_bp, url_prefix="/blog")
    # Blueprint sklepu zawiera:
    #   /                 -> shop.index
    #   /product/<id>     -> shop.product_detail
    #   /cart             -> shop.cart_view
    #   itd.
    app.register_blueprint(shop_bp)
    app.register_blueprint(webhooks_bp, url_prefix="/webhooks")

    # Dodanie kategorii:
    register_cli(app)

    return app
