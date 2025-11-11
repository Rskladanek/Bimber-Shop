from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length

class PostForm(FlaskForm):
    title = StringField("Tytuł", validators=[DataRequired(), Length(max=200)])
    category = SelectField("Kategoria", coerce=int, validators=[DataRequired()])
    content = TextAreaField("Treść", validators=[DataRequired(), Length(max=10000)])
    submit = SubmitField("Zapisz")
