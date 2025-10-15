from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired

class LoginForm(FlaskForm):
    username = StringField('Instagram Username', validators=[DataRequired()])
    password = PasswordField('Instagram Password', validators=[DataRequired()])
    submit = SubmitField('Login')
