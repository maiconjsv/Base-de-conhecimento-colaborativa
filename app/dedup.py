"""Verificador de documentos duplicados.

Um envio e considerado duplicado (e ignorado) quando:
1. o ARQUIVO e identico a um ja cadastrado (SHA-256 dos bytes), ou
2. o TEXTO extraido e o mesmo de um ja cadastrado, depois de normalizado
   (sem acento, minusculo, espacos colapsados). Pega o mesmo documento salvo
   de novo, renomeado ou exportado outra vez, cujos bytes mudam mas o conteudo nao.

A regra 2 so vale para textos com pelo menos MIN_TEXT_CHARS caracteres: textos
curtos ("Teste", "Ata") coincidem por acaso e nao provam duplicidade.

As impressoes ficam em `DocumentFingerprint` (tabela propria; a `document` nao
muda). Documentos cadastrados antes deste recurso recebem a impressao na
inicializacao, por `backfill_fingerprints`.
"""

import hashlib
import logging
import re
import unicodedata
from pathlib import Path

from .db import db

logger = logging.getLogger(__name__)

MIN_TEXT_CHARS = 200
_CHUNK = 1024 * 1024


class DuplicateDocument(Exception):
    """O arquivo enviado ja existe na base."""

    def __init__(self, existing, reason: str):
        super().__init__(f"duplicado de {existing.id} ({reason})")
        self.existing = existing
        self.reason = reason  # "arquivo" (identico) ou "conteudo" (mesmo texto)


def file_sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(_CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def text_sha256(text: str) -> str:
    """Impressao do texto normalizado, ou "" se for curto demais para comparar."""
    folded = "".join(
        c for c in unicodedata.normalize("NFD", (text or "").lower())
        if not unicodedata.combining(c)
    )
    norm = re.sub(r"\s+", " ", folded).strip()
    if len(norm) < MIN_TEXT_CHARS:
        return ""
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def find_duplicate(*, file_hash: str = "", text_hash: str = "", exclude_id: int | None = None):
    """(documento existente, motivo) ou (None, None)."""
    from .models import Document, DocumentFingerprint

    for column, value, reason in (
        (DocumentFingerprint.file_sha256, file_hash, "arquivo"),
        (DocumentFingerprint.text_sha256, text_hash, "conteudo"),
    ):
        if not value:
            continue
        query = db.session.query(Document).join(
            DocumentFingerprint, DocumentFingerprint.document_id == Document.id
        ).filter(column == value)
        if exclude_id is not None:
            query = query.filter(Document.id != exclude_id)
        existing = query.order_by(Document.id).first()
        if existing is not None:
            return existing, reason
    return None, None


def check_file(path: Path) -> str:
    """Hash do arquivo; levanta DuplicateDocument se ja existir igual."""
    file_hash = file_sha256(path)
    existing, reason = find_duplicate(file_hash=file_hash)
    if existing is not None:
        raise DuplicateDocument(existing, reason)
    return file_hash


def check_text(text: str) -> str:
    """Hash do texto; levanta DuplicateDocument se ja existir o mesmo conteudo."""
    text_hash = text_sha256(text)
    existing, reason = find_duplicate(text_hash=text_hash)
    if existing is not None:
        raise DuplicateDocument(existing, reason)
    return text_hash


def store_fingerprint(doc, *, file_hash: str, text_hash: str) -> None:
    """Grava/atualiza a impressao do documento. Sem commit."""
    from .models import DocumentFingerprint

    fp = doc.fingerprint
    if fp is None:
        doc.fingerprint = DocumentFingerprint(
            document_id=doc.id, file_sha256=file_hash, text_sha256=text_hash
        )
    else:
        fp.file_sha256, fp.text_sha256 = file_hash, text_hash


def backfill_fingerprints() -> int:
    """Calcula a impressao dos documentos que ainda nao tem. Devolve quantos."""
    from flask import current_app

    from .models import Document, DocumentFingerprint

    has_fp = db.session.query(DocumentFingerprint.document_id)
    pending = Document.query.filter(~Document.id.in_(has_fp)).all()
    upload_dir = Path(current_app.config["UPLOAD_DIR"])
    done = 0
    for doc in pending:
        path = upload_dir / doc.stored_filename
        if not path.exists():
            continue
        try:
            file_hash = file_sha256(path)
        except OSError:
            logger.exception("Falha ao ler %s para a impressao digital", path)
            continue
        store_fingerprint(
            doc,
            file_hash=file_hash,
            text_hash=text_sha256(doc.content) if doc.extraction_ok else "",
        )
        done += 1
    if done:
        db.session.commit()
        logger.info("%d documento(s) receberam impressao digital.", done)
    return done
