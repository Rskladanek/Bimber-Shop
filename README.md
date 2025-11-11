# Bimberek Białostocki

Projekt zaliczeniowy (Flask + PostgreSQL) łączący sklep internetowy z portalem społecznościowym.

## Stack

- Flask
- PostgreSQL + SQLAlchemy (Flask-SQLAlchemy)
- Flask-Login, Flask-WTF, Flask-Mail
- Authlib (logowanie przez Google / Facebook)
- Stripe (Checkout + webhook)
- Pillow (skalowanie obrazków)
- Jinja2 + Bootstrap 5

## Uruchomienie (dev)

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

export FLASK_APP=run.py
export FLASK_ENV=development

# Skonfiguruj bazę PostgreSQL i zmienną DATABASE_URL albo edytuj app/config.py

flask db init
flask db migrate -m "init"
flask db upgrade

flask run
```

W `.env` / zmiennych środowiskowych ustaw:

- `SECRET_KEY`
- `DATABASE_URL`
- `MAIL_*` (opcjonalnie)
- `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`
- `OAUTH_GOOGLE_CLIENT_ID`, `OAUTH_GOOGLE_CLIENT_SECRET`
- `OAUTH_FACEBOOK_CLIENT_ID`, `OAUTH_FACEBOOK_CLIENT_SECRET`
