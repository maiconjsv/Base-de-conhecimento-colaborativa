"""Paginas de erro amigaveis (403/404/413/500) no lugar das telas cruas."""

import logging

from flask import Flask, render_template
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)

_MESSAGES = {
    403: ("Acesso negado", "Você não tem permissão para acessar esta página."),
    404: ("Página não encontrada", "O endereço não existe ou o documento foi removido."),
    413: ("Arquivo grande demais", "O envio ultrapassa o limite permitido."),
    500: ("Erro interno", "Algo deu errado ao processar sua solicitação. Tente novamente."),
}


def _render(code: int, message: str | None = None):
    title, default_message = _MESSAGES.get(code, ("Erro", "Ocorreu um erro."))
    return (
        render_template(
            "errors/error.html", code=code, title=title, message=message or default_message
        ),
        code,
    )


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(403)
    def forbidden(_error):
        return _render(403)

    @app.errorhandler(404)
    def not_found(_error):
        return _render(404)

    @app.errorhandler(413)
    def too_large(_error):
        limit = app.config.get("MAX_CONTENT_LENGTH") or 0
        mb = limit // (1024 * 1024)
        msg = (
            f"O envio ultrapassa o limite de {mb} MB (somando todos os arquivos). "
            "Envie arquivos menores ou em lotes."
        )
        return _render(413, msg)

    @app.errorhandler(500)
    def server_error(error):
        logger.exception("Erro 500: %s", error)
        return _render(500)

    @app.errorhandler(Exception)
    def unhandled(error):
        if isinstance(error, HTTPException):
            return error  # 4xx ja tratados acima ou padrao do Flask
        logger.exception("Excecao nao tratada: %s", error)
        return _render(500)
