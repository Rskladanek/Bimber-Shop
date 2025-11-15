# app/auth/routes.py
# [POPRAWKA] Dodane importy dla 'session' i 'secrets'
from flask import render_template, redirect, url_for, flash, request, current_app, session
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_
import uuid
import secrets # [POPRAWKA] Dodany import do generowania nonce
import re # [POPRAWKA] Dodany import dla _find_or_create_oauth_user

from . import auth_bp
from .forms import RegistrationForm, LoginForm
from app.extensions import db, oauth
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
            if q is None:
                q = User.query.filter(User.email.ilike(f"{ident}%")).first()

        if not q or not check_password_hash(q.password_hash, form.password.data):
            flash("Nieprawidłowe dane logowania.", "danger")
            return render_template("auth/login.html", form=form), 401

        remember_me = form.remember_me.data
        login_user(q, remember=remember_me)
        
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


# ---------- Funkcja pomocnicza do tworzenia/logowania użytkownika OAuth ----------
def _find_or_create_oauth_user(provider_name: str, provider_user_id: str, user_info: dict):
    """
    Logika do wyszukiwania lub tworzenia użytkownika na podstawie danych z OAuth.
    Działa dla Google i Facebooka.
    """
    email = (user_info.get("email") or "").lower()
    name = user_info.get("name")
    
    # 1. Zbuduj zapytanie (logika scalania kont)
    query_filter = []
    
    # Pola specyficzne dla providera
    if provider_name == 'google' and hasattr(User, 'google_id'):
        query_filter.append(User.google_id == provider_user_id)
    elif provider_name == 'facebook' and hasattr(User, 'facebook_id'):
        query_filter.append(User.facebook_id == provider_user_id)
        
    # Zawsze sprawdzaj e-mail, jeśli jest dostępny
    if email:
        query_filter.append(User.email == email)
        
    if not query_filter:
        # Sytuacja awaryjna - brak ID i emaila?
        flash("Błąd logowania: Nie można uzyskać identyfikatora ani e-maila od dostawcy.", "danger")
        return None

    user = User.query.filter(or_(*query_filter)).first()

    # 2. Jeśli użytkownik nie istnieje - stwórz go
    if not user:
        if not email:
            flash(f"Logowanie przez {provider_name.capitalize()} wymaga udostępnienia adresu e-mail.", "danger")
            return None
            
        user = User(email=email)
        
        # Ustaw unikalną nazwę użytkownika (jeśli model jej wymaga)
        if hasattr(User, "username"):
            base = (name or email.split("@")[0]).replace(" ", "")
            # Szybka sanitacja nazwy, usunięcie niedozwolonych znaków
            candidate = re.sub(r"[^A-Za-z0-9_.\-]", "", base)[:30] or "user"
            
            i = 0
            while User.query.filter(User.username.ilike(candidate)).first():
                i += 1
                suffix = str(i)
                candidate = candidate[:(32 - len(suffix))] + suffix
            user.username = candidate

        if hasattr(User, "role") and not getattr(user, "role", None):
            user.role = "user"
            
        # Ustaw losowe hasło (konto nie będzie logowane lokalnie hasłem)
        random_pass = str(uuid.uuid4())
        user.password_hash = generate_password_hash(random_pass)

        # Ustaw ID providera
        if provider_name == 'google' and hasattr(User, 'google_id'):
            user.google_id = provider_user_id
        elif provider_name == 'facebook' and hasattr(User, 'facebook_id'):
            user.facebook_id = provider_user_id

        db.session.add(user)
        # Commit jest potrzebny teraz, aby zakończyć transakcję i móc zalogować
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Błąd tworzenia użytkownika OAuth: {e}")
            flash("Wystąpił błąd podczas tworzenia konta.", "danger")
            return None
            
    # 3. Jeśli użytkownik istnieje - uzupełnij brakujące ID (scalanie)
    else:
        needs_commit = False
        if provider_name == 'google' and hasattr(User, 'google_id') and not user.google_id:
            user.google_id = provider_user_id
            needs_commit = True
        elif provider_name == 'facebook' and hasattr(User, 'facebook_id') and not user.facebook_id:
            user.facebook_id = provider_user_id
            needs_commit = True
            
        if needs_commit:
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Błąd scalania konta OAuth: {e}")
                flash("Wystąpił błąd podczas łączenia konta.", "danger")
                return None

    # 4. Zaloguj użytkownika (zawsze bez "remember me" dla OAuth)
    login_user(user, remember=False)
    return user


# ---------- Google OAuth (Authlib) ----------
@auth_bp.route("/google/login")
def google_login():
    if not current_app.config.get("GOOGLE_CLIENT_ID"):
        flash("Logowanie Google nie jest skonfigurowane.", "warning")
        return redirect(url_for("auth.login"))
    redirect_uri = url_for("auth.google_callback", _external=True)
    
    # [POPRAWKA 1] Wygeneruj i zapisz nonce w sesji
    nonce = secrets.token_urlsafe(16)
    session['google_oauth_nonce'] = nonce
    
    return oauth.google.authorize_redirect(redirect_uri, nonce=nonce)


@auth_bp.route("/google/callback")
def google_callback():
    if not current_app.config.get("GOOGLE_CLIENT_ID"):
        return redirect(url_for("auth.login"))

    try:
        token = oauth.google.authorize_access_token()
        
        # [POPRAWKA 2] Pobierz nonce z sesji
        nonce = session.pop('google_oauth_nonce', None)
        if not nonce:
            raise Exception("Brak 'nonce' w sesji. Możliwa próba ataku CSRF.")
            
        # [POPRAWKA 3] Przekaż nonce do weryfikacji
        userinfo = oauth.google.parse_id_token(token, nonce=nonce)
        
    except Exception as e:
        current_app.logger.error(f"Błąd autoryzacji Google: {e}")
        # [POPRAWKA 4] Pokaż faktyczny błąd, aby ułatwić debugowanie
        flash(f"Błąd logowania przez Google: {str(e)}. Spróbuj ponownie.", "danger")
        return redirect(url_for("auth.login"))

    if not userinfo:
        flash("Błąd logowania przez Google: Nie uzyskano danych.", "danger")
        return redirect(url_for("auth.login"))

    google_sub = userinfo.get("sub") # 'sub' to standardowe pole ID w OpenID
    
    user = _find_or_create_oauth_user(
        provider_name='google',
        provider_user_id=google_sub,
        user_info=userinfo
    )

    if user:
        flash("Zalogowano przez Google.", "success")
        return redirect(url_for("shop.index"))
    else:
        return redirect(url_for("auth.login"))


# ---------- Facebook OAuth (Authlib) ----------
@auth_bp.route("/facebook/login")
def facebook_login():
    if not current_app.config.get("FACEBOOK_CLIENT_ID"):
        flash("Logowanie Facebook nie jest skonfigurowane.", "warning")
        return redirect(url_for("auth.login"))
    redirect_uri = url_for("auth.facebook_callback", _external=True)
    return oauth.facebook.authorize_redirect(redirect_uri)


@auth_bp.route("/facebook/callback")
def facebook_callback():
    if not current_app.config.get("FACEBOOK_CLIENT_ID"):
        return redirect(url_for("auth.login"))

    try:
        token = oauth.facebook.authorize_access_token()
        # Dla Facebooka musimy ręcznie pobrać dane profilu
        resp = oauth.facebook.get('me?fields=id,name,email', token=token)
        resp.raise_for_status() # Rzuci błędem jeśli API Facebooka zwróci błąd
        userinfo = resp.json()
        
    except Exception as e:
        current_app.logger.error(f"Błąd autoryzacji Facebook: {e}")
        flash("Błąd logowania przez Facebook. Spróbuj ponownie.", "danger")
        return redirect(url_for("auth.login"))

    if not userinfo or not userinfo.get("id"):
        flash("Błąd logowania przez Facebook: Nie uzyskano danych.", "danger")
        return redirect(url_for("auth.login"))

    facebook_id = userinfo.get("id")

    user = _find_or_create_oauth_user(
        provider_name='facebook',
        provider_user_id=facebook_id,
        user_info=userinfo
    )
    
    if user:
        flash("Zalogowano przez Facebook.", "success")
        return redirect(url_for("shop.index"))
    else:
        return redirect(url_for("auth.login"))