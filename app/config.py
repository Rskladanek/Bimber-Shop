import os

# Bazowy katalog projektu (folder "app")
BASEDIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # --- Flask / bezpieczeństwo ---
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")

    # --- Baza danych ---
    # 1) jeśli ustawisz zmienną środowiskową DATABASE_URL (np. na PostgreSQL),
    #    to ona ma pierwszeństwo
    # 2) inaczej używamy lokalnej bazy SQLite w katalogu "instance/bimberek.db"
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(BASEDIR, "..", "instance", "bimberek.db"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Mail (opcjonalnie, używane przy powiadomieniach o płatności) ---
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "localhost")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 25))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "false").lower() in (
        "true",
        "1",
        "t",
        "yes",
        "y",
    )
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get(
        "MAIL_DEFAULT_SENDER",
        "sklep@bimberek.local",
    )

    # --- Stripe (płatności) ---
    STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")
    STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY")
    STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")

    # --- Google OAuth (Authlib) ---
    # Obsługujemy obie nazwy zmiennych, żeby zgadzało się z README:
    # - GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET
    # - OAUTH_GOOGLE_CLIENT_ID / OAUTH_GOOGLE_CLIENT_SECRET
    GOOGLE_CLIENT_ID = (
        os.environ.get("GOOGLE_CLIENT_ID")
        or os.environ.get("OAUTH_GOOGLE_CLIENT_ID", "")
    )
    GOOGLE_CLIENT_SECRET = (
        os.environ.get("GOOGLE_CLIENT_SECRET")
        or os.environ.get("OAUTH_GOOGLE_CLIENT_SECRET", "")
    )

    # [ZMIANA] Dodane klucze dla Facebook OAuth
    FACEBOOK_CLIENT_ID = os.environ.get("FACEBOOK_CLIENT_ID", "")
    FACEBOOK_CLIENT_SECRET = os.environ.get("FACEBOOK_CLIENT_SECRET", "")
