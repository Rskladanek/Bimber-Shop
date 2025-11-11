# create_admin.py
"""
Jednorazowy skrypt:
- tworzy brakujące tabele w bazie (db.create_all)
- zakłada konto admina, jeśli go nie ma
"""

from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import User


ADMIN_EMAIL = "admin@bimberek.local"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "MegaMocneHaslo!123"  # zmień jak chcesz


def main():
    app = create_app()

    with app.app_context():
        # 1) Tworzymy WSZYSTKIE tabele według modeli
        print("[*] Tworzę brakujące tabele w bazie (db.create_all)...")
        db.create_all()

        # 2) Sprawdzamy, czy admin już istnieje
        user = User.query.filter_by(email=ADMIN_EMAIL).first()
        if user:
            print(f"[=] Użytkownik z mailem {ADMIN_EMAIL} już istnieje (id={user.id}).")
            if hasattr(User, "role"):
                print(f"    Rola: {getattr(user, 'role', None)}")
            return

        print(f"[*] Tworzę nowego admina: {ADMIN_EMAIL} / {ADMIN_USERNAME}")
        user = User(email=ADMIN_EMAIL)

        if hasattr(User, "username"):
            user.username = ADMIN_USERNAME

        # rola admin, jeśli model to wspiera
        if hasattr(User, "role"):
            user.role = "admin"

        # hasło
        user.password_hash = generate_password_hash(ADMIN_PASSWORD)

        db.session.add(user)
        db.session.commit()

        print(f"[+] Admin utworzony. ID={user.id}")
        print("    Zalogujesz się tymi danymi:")
        print(f"    login: {ADMIN_EMAIL} lub {ADMIN_USERNAME}")
        print(f"    hasło: {ADMIN_PASSWORD}")


if __name__ == "__main__":
    main()
