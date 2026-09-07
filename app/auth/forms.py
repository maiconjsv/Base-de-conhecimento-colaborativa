from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length, Regexp


class LoginForm(FlaskForm):
    username = StringField("Usuario", validators=[DataRequired()])
    password = PasswordField("Senha", validators=[DataRequired()])
    remember = BooleanField("Manter conectado")
    submit = SubmitField("Entrar")


class RegisterForm(FlaskForm):
    username = StringField(
        "Usuario",
        validators=[
            DataRequired(),
            Length(min=3, max=80),
            Regexp(
                r"^[A-Za-z0-9._-]+$",
                message="Use apenas letras, numeros, ponto, hifen ou sublinhado.",
            ),
        ],
    )
    password = PasswordField(
        "Senha", validators=[DataRequired(), Length(min=6, message="Minimo 6 caracteres.")]
    )
    confirm = PasswordField(
        "Confirme a senha",
        validators=[DataRequired(), EqualTo("password", message="As senhas nao conferem.")],
    )
    submit = SubmitField("Criar conta")
