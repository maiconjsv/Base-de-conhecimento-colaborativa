"""Regras de negocio para upload, reprocessamento e remocao de documentos."""

import logging
import mimetypes
import uuid
from pathlib import Path

from flask import current_app
from werkzeug.utils import secure_filename

from ..db import db
from ..extract import extract_doc_meta, extract_text
from ..images import extract_images
from ..models import Document, DocumentImage
from .analyze import derive_metadata

logger = logging.getLogger(__name__)


def _ext(filename: str) -> str:
    return Path(filename).suffix.lower().lstrip(".")


def _upload_dir() -> Path:
    return Path(current_app.config["UPLOAD_DIR"])


def _image_dir() -> Path:
    return Path(current_app.config["IMAGE_DIR"])


def ingest_file(file_storage, *, user_id: int) -> Document:
    """Salva o arquivo e monta o registro extraindo tudo automaticamente."""
    original = secure_filename(file_storage.filename) or "arquivo"
    ext = _ext(original)
    stored = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
    dest = _upload_dir() / stored

    file_storage.save(dest)
    size = dest.stat().st_size

    text, ok = extract_text(dest, ext)
    embedded = extract_doc_meta(dest, ext)
    meta = derive_metadata(original_filename=original, text=text, embedded=embedded)

    doc = Document(
        title=meta["title"],
        description=meta["description"],
        tags=meta["tags"],
        original_filename=original,
        stored_filename=stored,
        mime_type=mimetypes.guess_type(original)[0] or "",
        file_size=size,
        content=text,
        extraction_ok=ok,
        uploaded_by=user_id,
    )
    db.session.add(doc)
    db.session.flush()  # garante doc.id para as imagens

    n_images = _store_images(doc, dest, ext)
    db.session.commit()
    logger.info(
        "Documento %s salvo: titulo=%r, %d chars, %d imagem(ns), extraction_ok=%s",
        doc.id, doc.title, len(text), n_images, ok,
    )
    return doc


def _store_images(doc: Document, source_path: Path, ext: str) -> int:
    """Extrai as imagens embutidas e grava em disco + banco. Nao faz commit."""
    if not current_app.config.get("EXTRACT_IMAGES", True):
        return 0
    try:
        images = extract_images(source_path, ext)
    except Exception:  # noqa: BLE001 - best effort
        logger.exception("Extracao de imagens falhou para documento %s", doc.id)
        return 0

    image_dir = _image_dir()
    for ordinal, img in enumerate(images):
        key = uuid.uuid4().hex
        full_name = f"{key}.{img['ext']}"
        thumb_name = f"{key}_thumb.{img['thumb_ext']}"
        try:
            (image_dir / full_name).write_bytes(img["data"])
            (image_dir / thumb_name).write_bytes(img["thumb_data"])
        except OSError:
            logger.exception("Falha ao gravar imagem extraida de %s", doc.id)
            continue
        db.session.add(DocumentImage(
            document_id=doc.id,
            stored_filename=full_name,
            thumb_filename=thumb_name,
            content_type=img["content_type"],
            width=img["width"],
            height=img["height"],
            ordinal=ordinal,
            source_ref=img["ref"],
        ))
    return len(doc.images)


def _remove_image_files(images) -> None:
    image_dir = _image_dir()
    for img in images:
        for name in (img.stored_filename, img.thumb_filename):
            try:
                (image_dir / name).unlink(missing_ok=True)
            except OSError:
                logger.exception("Falha ao remover imagem %s", name)


def reprocess_document(doc: Document) -> None:
    """Re-extrai texto e imagens do arquivo em disco. Nao faz commit.

    Preserva titulo/descricao/tags (podem ter sido ajustados manualmente).
    """
    path = _upload_dir() / doc.stored_filename
    if not path.exists():
        logger.warning("Arquivo ausente para documento %s: %s", doc.id, path)
        return
    ext = _ext(doc.stored_filename)
    text, ok = extract_text(path, ext)
    doc.content = text
    doc.extraction_ok = ok

    _remove_image_files(list(doc.images))
    doc.images.clear()
    db.session.flush()
    _store_images(doc, path, ext)


def delete_document(doc: Document) -> None:
    _remove_image_files(list(doc.images))
    path = _upload_dir() / doc.stored_filename
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.exception("Falha ao remover arquivo %s", path)
    db.session.delete(doc)
    db.session.commit()
