from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileRequired, MultipleFileField
from wtforms import StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional

ALLOWED = [
    "pdf", "doc", "docx", "txt", "md", "markdown",
    "xls", "xlsx", "xlsm", "ppt", "pptx", "csv",
]


class UploadForm(FlaskForm):
    files = MultipleFileField(
        "Arquivos",
        validators=[
            FileRequired("Selecione ou arraste ao menos um arquivo."),
            FileAllowed(ALLOWED, "Ha um arquivo em formato nao suportado na selecao."),
        ],
    )
    submit = SubmitField("Enviar")


class EditForm(FlaskForm):
    title = StringField("Titulo", validators=[DataRequired(), Length(max=255)])
    description = TextAreaField("Descricao", validators=[Optional(), Length(max=5000)])
    tags = StringField("Tags", validators=[Optional(), Length(max=500)])
    submit = SubmitField("Salvar")


class DeleteForm(FlaskForm):
    """Somente para transportar o token CSRF do botao de remover."""

    submit = SubmitField("Remover")
