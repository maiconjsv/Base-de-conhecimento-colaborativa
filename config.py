"""Configuracao da aplicacao.

Modo normal (desenvolvimento):   banco em instance/kb.sqlite, arquivos em uploads/
Modo portatil (KB_DATA_DIR set): tudo dentro dessa pasta -> kb.sqlite, uploads/,
secret.key. E o modo usado pelo executavel: a pasta "dados" ao lado do .exe
carrega todo o estado, entao basta zipar a pasta para distribuir.
"""

import os
import secrets
import sys
from pathlib import Path

from dotenv import load_dotenv

if getattr(sys, "frozen", False):
    # Programa empacotado: so considera um .env colocado ao lado do .exe.
    _exe_env = Path(sys.executable).resolve().parent / ".env"
    if _exe_env.exists():
        load_dotenv(_exe_env)
else:
    load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

_DATA_DIR_ENV = os.environ.get("KB_DATA_DIR")
DATA_DIR = Path(_DATA_DIR_ENV) if _DATA_DIR_ENV else None


def _resolve_secret_key() -> str:
    """SECRET_KEY do ambiente; senao um arquivo persistente na pasta de dados."""
    from_env = os.environ.get("SECRET_KEY")
    if from_env:
        return from_env
    if DATA_DIR is not None:
        key_file = DATA_DIR / "secret.key"
        try:
            if key_file.exists():
                return key_file.read_text(encoding="utf-8").strip()
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            value = secrets.token_urlsafe(48)
            key_file.write_text(value, encoding="utf-8")
            return value
        except OSError:
            pass
    return "dev-key-troque-em-producao"


class Config:
    SECRET_KEY = _resolve_secret_key()

    if DATA_DIR is not None:
        INSTANCE_DIR = DATA_DIR
        UPLOAD_DIR = DATA_DIR / "uploads"
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{(DATA_DIR / 'kb.sqlite').as_posix()}"
    else:
        INSTANCE_DIR = BASE_DIR / "instance"
        UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", BASE_DIR / "uploads"))
        SQLALCHEMY_DATABASE_URI = os.environ.get(
            "DATABASE_URL", f"sqlite:///{INSTANCE_DIR / 'kb.sqlite'}"
        )

    # Imagens extraidas de dentro dos documentos
    IMAGE_DIR = UPLOAD_DIR / "images"
    # Extrair imagens embutidas em PDF/DOCX/PPTX/XLSX no upload
    EXTRACT_IMAGES = os.environ.get("EXTRACT_IMAGES", "1") != "0"

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Tamanho maximo do envio (somando todos os arquivos): 50 MB
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 50 * 1024 * 1024))

    ALLOWED_EXTENSIONS = {
        "pdf", "doc", "docx", "txt", "md", "markdown",
        "xls", "xlsx", "ppt", "pptx", "csv",
    }

    # Resultados por pagina na busca
    PAGE_SIZE = 10
