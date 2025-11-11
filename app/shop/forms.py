from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    TextAreaField,
    DecimalField,
    SelectField,
    IntegerField,
    FileField,
    SubmitField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional
from flask_wtf.file import FileAllowed


class ProductForm(FlaskForm):
    """Formularz produktu używany w panelu admina."""

    name = StringField(
        "Nazwa",
        validators=[DataRequired(message="Podaj nazwę produktu."), Length(max=120)],
    )

    price = DecimalField(
        "Cena (PLN)",
        places=2,
        validators=[
            DataRequired(message="Podaj cenę."),
            NumberRange(min=0, message="Cena nie może być ujemna."),
        ],
    )

    # Kategoria – OPCJONALNA.
    # Admin routes ustawiają:
    #   form.category.choices = [(0, '--- brak kategorii ---'), (id, nazwa)...]
    # i później:
    #   category_id = form.category.data or None
    #
    # Dzięki brakowi DataRequired można spokojnie zostawić 0
    # i produkt zapisze się bez kategorii.
    category = SelectField(
        "Kategoria",
        coerce=int,
        validators=[Optional()],
    )

    # Opis – opcjonalny, do 2000 znaków
    description = TextAreaField(
        "Opis",
        validators=[Optional(), Length(max=2000)],
    )

    # Ilość w magazynie – opcjonalna, >= 0
    stock = IntegerField(
        "Ilość w magazynie",
        validators=[Optional(), NumberRange(min=0, message="Ilość nie może być ujemna.")],
        default=0,
    )

    image = FileField(
        "Zdjęcie",
        validators=[
            Optional(),
            FileAllowed(
                ["jpg", "jpeg", "png", "gif"],
                "Dozwolone formaty: JPG, JPEG, PNG, GIF.",
            ),
        ],
    )

    submit = SubmitField("Zapisz produkt")


class CommentForm(FlaskForm):
    content = TextAreaField(
        "Twój komentarz",
        validators=[DataRequired(message="Komentarz nie może być pusty."), Length(min=3)],
    )
    submit = SubmitField("Dodaj komentarz")


class CheckoutForm(FlaskForm):
    address = StringField(
        "Adres wysyłki",
        validators=[DataRequired(message="Podaj adres wysyłki."), Length(max=250)],
    )
    submit = SubmitField("Złóż zamówienie")
