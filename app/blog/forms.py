from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length


class PostForm(FlaskForm):
    title = StringField("Tytuł", validators=[DataRequired(), Length(max=200)])
    content = TextAreaField("Treść", validators=[DataRequired(), Length(max=10000)])
    submit = SubmitField("Zapisz")


class BlogCommentForm(FlaskForm):
    content = TextAreaField(
        "Twój komentarz",
        validators=[DataRequired(message="Komentarz nie może być pusty."), Length(min=3)],
    )
    submit = SubmitField("Dodaj komentarz")
