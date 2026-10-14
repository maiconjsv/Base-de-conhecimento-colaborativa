import logging
import sys
from pathlib import Path

import click
from flask import Flask, redirect, request, url_for
from flask_login import LoginManager

from config import Config

from .db import create_fts, db, init_engine_pragmas, rebuild_fts

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Faca login para acessar esta pagina."


def _make_flask() -> Flask:
    """Quando empacotado (PyInstaller), templates/static vem de _MEIPASS."""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return Flask(
            __name__,
            template_folder=str(base / "app" / "templates"),
            static_folder=str(base / "app" / "static"),
        )
    return Flask(__name__)


def create_app(config_class: type = Config) -> Flask:
    app = _make_flask()
    app.config.from_object(config_class)

    logging.basicConfig(level=logging.INFO)

    # Diretorios necessarios
    app.config["INSTANCE_DIR"].mkdir(parents=True, exist_ok=True)
    app.config["UPLOAD_DIR"].mkdir(parents=True, exist_ok=True)
    app.config["IMAGE_DIR"].mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    from .llm import engine as llm_engine

    llm_engine.log_path = app.config["INSTANCE_DIR"] / "ia.log"

    with app.app_context():
        init_engine_pragmas(db.engine)

    from .models import User

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    from .auth import bp as auth_bp
    from .documents import bp as documents_bp
    from .notes import bp as notes_bp
    from .errors import register_error_handlers

    app.register_blueprint(auth_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(notes_bp)
    register_error_handlers(app)

    @app.context_processor
    def _inject_contact():
        return {
            "support_email": app.config["SUPPORT_EMAIL"],
            "github_user": app.config["GITHUB_USER"],
            "github_repo": app.config["GITHUB_REPO"],
        }

    @app.before_request
    def _require_first_admin():
        # Primeiro uso: sem nenhum usuario cadastrado, tudo leva para /setup.
        if request.endpoint in ("auth.setup", "static", "documents.contribute") or request.endpoint is None:
            return None
        try:
            has_user = db.session.query(User.id).first() is not None
        except Exception:  # noqa: BLE001 - banco ainda nao inicializado
            return None
        if not has_user:
            return redirect(url_for("auth.setup"))
        return None

    _register_cli(app)
    return app


def _register_cli(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db() -> None:
        """Cria as tabelas, o indice FTS5 e os triggers."""
        from .dedup import backfill_fingerprints
        from .sheets import backfill_sheets

        db.create_all()
        create_fts(db.session)
        backfill_sheets()
        backfill_fingerprints()
        click.echo("Banco e indice de busca prontos.")

    @app.cli.command("create-user")
    @click.argument("username")
    @click.password_option()
    def create_user(username: str, password: str) -> None:
        """Cria um usuario. Ex: flask --app run.py create-user master"""
        from .models import User

        if User.query.filter_by(username=username).first():
            raise click.ClickException(f"Ja existe o usuario {username}.")
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Usuario {username} criado.")

    @app.cli.command("reindex")
    def reindex() -> None:
        """Reprocessa os arquivos e reconstroi o indice de busca."""
        from .documents.service import reprocess_document
        from .models import Document

        docs = Document.query.all()
        for doc in docs:
            reprocess_document(doc)
        db.session.commit()
        rebuild_fts(db.session)
        click.echo(f"{len(docs)} documento(s) reprocessado(s).")
