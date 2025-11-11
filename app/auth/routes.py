# app/auth/routes.py
from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_

from . import auth_bp
from .forms import RegistrationForm, LoginForm
from app.extensions import db, oauth  # patrz sekcja 4 – init OAuth
from app.models import User

# ---------- Rejestracja ----------
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("shop.index"))

    form = RegistrationForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        username = form.username.data.strip()

        user = User(
            email=email,
        )
        # ustaw username tylko jeśli model ma taką kolumnę
        if hasattr(User, "username"):
            user.username = username

        user.password_hash = generate_password_hash(form.password.data)

        # ustaw domyślną rolę, jeśli masz (np. "user")
        if hasattr(User, "role") and not getattr(user, "role", None):
            user.role = "user"

        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Konto utworzone. Witaj!", "success")
        return redirect(url_for("shop.index"))

    return render_template("auth/register.html", form=form)


# ---------- Logowanie ----------
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("shop.index"))

    form = LoginForm()
    if form.validate_on_submit():
        ident = (form.identifier.data or "").strip()
        q = None
        if "@" in ident:
            q = User.query.filter_by(email=ident.lower()).first()
        else:
            if hasattr(User, "username"):
                q = User.query.filter(User.username.ilike(ident)).first()
            # fallback na e-mail, jeśli ktoś podał bez @ (np. lokalna część)
            if q is None:
                q = User.query.filter(User.email.ilike(f"{ident}%")).first()

        if not q or not check_password_hash(q.password_hash, form.password.data):
            flash("Nieprawidłowe dane logowania.", "danger")
            return render_template("auth/login.html", form=form), 401

        login_user(q)
        flash("Zalogowano.", "success")
        next_url = request.args.get("next")
        return redirect(next_url or url_for("shop.index"))

    return render_template("auth/login.html", form=form)


# ---------- Wylogowanie ----------
@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Wylogowano.", "info")
    return redirect(url_for("shop.index"))


# ---------- Google OAuth (Authlib) ----------
@auth_bp.route("/google/login")
def google_login():
    # zabezpieczenie: brak konfiguracji → wyłącz przycisk
    if not current_app.config.get("GOOGLE_CLIENT_ID"):
        flash("Logowanie Google nie jest skonfigurowane.", "warning")
        return redirect(url_for("auth.login"))
    redirect_uri = url_for("auth.google_callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route("/google/callback")
def google_callback():
    if not current_app.config.get("GOOGLE_CLIENT_ID"):
        flash("Logowanie Google nie jest skonfigurowane.", "warning")
        return redirect(url_for("auth.login"))

    token = oauth.google.authorize_access_token()
    userinfo = oauth.google.parse_id_token(token)

    if not userinfo:
        flash("Błąd logowania przez Google.", "danger")
        return redirect(url_for("auth.login"))

    google_sub = userinfo.get("sub")
    email = (userinfo.get("email") or "").lower()
    name = userinfo.get("name") or (email.split("@")[0] if email else None)

    # Szukamy po google_id lub mailu (scalanie kont)
    user = None
    if hasattr(User, "google_id"):
        user = User.query.filter(
            or_(User.google_id == google_sub, User.email == email)
        ).first()
    else:
        user = User.query.filter_by(email=email).first()

    if not user:
        user = User(email=email)
        if hasattr(User, "username"):
            base = (name or email.split("@")[0]).replace(" ", "")
            candidate = base[:32] if base else "user"
            # prosty unik nazw – dokładamy liczby, aż zaskoczy
            if hasattr(User, "username"):
                i = 0
                while User.query.filter(User.username.ilike(candidate)).first():
                    i += 1
                    candidate = (base + str(i))[:32]
                user.username = candidate
        if hasattr(User, "role") and not getattr(user, "role", None):
            user.role = "user"
        # pusta “losowa” blokada hasła lokalnego (nie logujemy hasłem)
        user.password_hash = generate_password_hash(token["access_token"][:16])

        if hasattr(User, "google_id"):
            user.google_id = google_sub

        db.session.add(user)
        db.session.commit()
    else:
        # uzupełnij google_id jeśli brak
        if hasattr(User, "google_id") and not getattr(user, "google_id", None):
            user.google_id = google_sub
            db.session.commit()

    login_user(user)
    flash("Zalogowano przez Google.", "success")
    return redirect(url_for("shop.index"))
