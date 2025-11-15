# app/auth/forms.py
from wtforms import StringField, PasswordField, SubmitField, BooleanField  # [ZMIANA] Import BooleanField
from wtforms.fields import EmailField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from flask_wtf import FlaskForm
import re

from app.models import User  # musi istnieć model User


USERNAME_REGEX = re.compile(r"^[A-Za-z0-9_.\-@!$%^&*+=ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]{3,32}$")


def validate_password_policy(_, field):
    """Min. 10 znaków, min. 1 mała, 1 duża, 1 cyfra, 1 znak specjalny."""
    pwd = field.data or ""
    if len(pwd) < 10:
        raise ValidationError("Hasło musi mieć co najmniej 10 znaków.")
    if not re.search(r"[a-z]", pwd):
        raise ValidationError("Hasło musi zawierać małą literę.")
    if not re.search(r"[A-Z]", pwd):
        raise ValidationError("Hasło musi zawierać wielką literę.")
    if not re.search(r"\d", pwd):
        raise ValidationError("Hasło musi zawierać cyfrę.")
    if not re.search(r"[^\w\s]", pwd):
        raise ValidationError("Hasło musi zawierać znak specjalny.")


class RegistrationForm(FlaskForm):
    username = StringField(
        "Nazwa użytkownika",
        validators=[DataRequired(), Length(min=3, max=32)],
    )
    email = EmailField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("Hasło", validators=[DataRequired(), validate_password_policy])
    confirm_password = PasswordField(
        "Powtórz hasło",
        validators=[DataRequired(), EqualTo("password", message="Hasła muszą się zgadzać.")],
    )
    submit = SubmitField("Zarejestruj się")

    def validate_username(self, field):
        val = (field.data or "").strip()
        if not USERNAME_REGEX.match(val):
            raise ValidationError(
                "Dozwolone litery/cyfry oraz . _ - @ ! $ % ^ & * + =, bez spacji (3–32 znaki)."
            )
        # unikalność, jeśli kolumna istnieje
        if hasattr(User, "username"):
            if User.query.filter(User.username.ilike(val)).first():
                raise ValidationError("Taka nazwa użytkownika już istnieje.")

    def validate_email(self, field):
        val = (field.data or "").strip().lower()
        if User.query.filter_by(email=val).first():
            raise ValidationError("Ten adres e-mail jest już zajęty.")


class LoginForm(FlaskForm):
    identifier = StringField("Email lub nazwa użytkownika", validators=[DataRequired()])
    password = PasswordField("Hasło", validators=[DataRequired()])
    # [ZMIANA] Dodane pole "Pamiętaj mnie" (Token 4.0)
    remember_me = BooleanField("Nie wylogowuj mnie")
    submit = SubmitField("Zaloguj się")
