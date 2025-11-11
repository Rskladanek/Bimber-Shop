# app/admin/forms.py

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (
    StringField,
    TextAreaField,
    DecimalField,
    IntegerField,
    SelectField,
    BooleanField,
    SubmitField,
)
from wtforms.validators import (
    DataRequired,
    Optional,
    NumberRange,
    Length,
)


class ProductForm(FlaskForm):
    """Formularz dodawania / edycji produktu w panelu admina."""

    name = StringField(
        "Nazwa",
        validators=[DataRequired(message="Podaj nazwę produktu."), Length(max=255)],
    )

    price = DecimalField(
        "Cena (PLN)",
        places=2,
        rounding=None,
        validators=[
            DataRequired(message="Podaj cenę."),
            NumberRange(min=0, message="Cena nie może być ujemna."),
        ],
    )

    # Ilość w magazynie – opcjonalna, domyślnie 0
    stock = IntegerField(
        "Ilość w magazynie",
        default=0,
        validators=[
            Optional(),
            NumberRange(min=0, message="Ilość nie może być ujemna."),
        ],
    )

    # Uwaga: walidator dokładamy dynamicznie w __init__
    category = SelectField(
        "Kategoria",
        coerce=int,
    )

    description = TextAreaField(
        "Opis",
        validators=[Optional()],
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

    def __init__(self, *args, **kwargs):
        """
        Dynamicznie ustawiamy listę kategorii i walidator:

        - jeśli są kategorie w bazie:
            * choices = [(id, nazwa), ...]
            * category jest WYMAGANA (DataRequired)
        - jeśli NIE ma żadnej kategorii:
            * choices = [(0, '--- brak kategorii ---')]
            * category jest OPCJONALNA (brak DataRequired)

        Dzięki temu:
        - przy pustej tabeli categories można normalnie zapisywać produkt,
        - jak już dodasz kategorie, formularz zacznie je wymagać.
        """
        super().__init__(*args, **kwargs)

        try:
            from app.models import Category

            categories = Category.query.order_by(Category.name).all()
        except Exception:
            categories = []

        if categories:
            self.category.choices = [(c.id, c.name) for c in categories]
            self.category.validators = [DataRequired(message="Wybierz kategorię.")]
        else:
            self.category.choices = [(0, "--- brak kategorii ---")]
            self.category.validators = []  # brak wymogu – kategoria opcjonalna


class SliderForm(FlaskForm):
    """Formularz slidera (główny baner na stronie sklepu)."""

    name = StringField(
        "Nazwa slidera",
        validators=[DataRequired(message="Podaj nazwę slidera."), Length(max=255)],
    )
    is_active = BooleanField("Aktywny")
    submit = SubmitField("Zapisz slider")


class SliderItemForm(FlaskForm):
    """Formularz pojedynczego slajdu w sliderze."""

    title = StringField("Nagłówek", validators=[Optional(), Length(max=255)])
    subtitle = StringField("Podtytuł", validators=[Optional(), Length(max=255)])
    button_label = StringField(
        "Tekst przycisku",
        validators=[Optional(), Length(max=128)],
    )
    button_url = StringField(
        "Link przycisku",
        validators=[Optional(), Length(max=512)],
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
    order_index = IntegerField(
        "Kolejność",
        default=0,
        validators=[Optional(), NumberRange(min=0, message="Kolejność ≥ 0.")],
    )
    is_active = BooleanField("Aktywny")
    submit = SubmitField("Zapisz slajd")


class ThemeForm(FlaskForm):
    """Formularz motywu kolorystycznego sklepu."""

    name = StringField(
        "Nazwa motywu",
        validators=[DataRequired(message="Podaj nazwę motywu."), Length(max=100)],
    )
    primary_color = StringField(
        "Kolor główny (HEX)",
        validators=[Optional(), Length(max=7)],
    )
    secondary_color = StringField(
        "Kolor dodatkowy (HEX)",
        validators=[Optional(), Length(max=7)],
    )
    background_color = StringField(
        "Kolor tła (HEX)",
        validators=[Optional(), Length(max=7)],
    )
    text_color = StringField(
        "Kolor tekstu (HEX)",
        validators=[Optional(), Length(max=7)],
    )
    is_default = BooleanField("Ustaw jako domyślny motyw")
    submit = SubmitField("Zapisz motyw")
