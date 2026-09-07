"""Busca full-text sobre o indice SQLite FTS5."""

import re

from sqlalchemy import text

from .db import db
from .locator import compile_terms, count_matches
from .models import Document

# Palavras/tokens: letras e numeros em qualquer idioma, sem underscore.
_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)


def tokenize(raw: str) -> list[str]:
    """Termos da busca, do jeito que o FTS os enxerga."""
    return _TOKEN_RE.findall(raw or "")


def build_match_query(raw: str) -> str:
    """Converte a entrada do usuario em uma expressao MATCH segura do FTS5.

    Cada termo vira um literal entre aspas com sufixo `*` (busca por prefixo),
    combinados por AND implicito. Assim caracteres especiais do FTS5 nunca
    chegam crus ao parser.
    """
    tokens = tokenize(raw)
    if not tokens:
        return ""
    return " ".join(f'"{tok}"*' for tok in tokens)


def _hit_count(doc: Document, term_re) -> int:
    """Quantas vezes os termos aparecem no documento (conteudo + metadados)."""
    if term_re is None:
        return 0
    return (
        count_matches(doc.title, term_re)
        + count_matches(doc.description, term_re)
        + count_matches(doc.tags, term_re)
        + count_matches(doc.content, term_re)
    )


def search_documents(raw_query: str, page: int = 1, page_size: int = 10):
    """Retorna (items, total).

    Cada item: {document, snippet (HTML do melhor trecho), hit_count}.
    """
    match = build_match_query(raw_query)
    if not match:
        return [], 0

    page = max(page, 1)
    offset = (page - 1) * page_size

    total = db.session.execute(
        text("SELECT count(*) FROM document_fts WHERE document_fts MATCH :m"),
        {"m": match},
    ).scalar_one()

    rows = db.session.execute(
        text(
            """
            SELECT rowid AS doc_id,
                   snippet(document_fts, -1, '<mark>', '</mark>', ' … ', 20) AS snip
            FROM document_fts
            WHERE document_fts MATCH :m
            ORDER BY bm25(document_fts, 8.0, 4.0, 6.0, 1.0)
            LIMIT :limit OFFSET :offset
            """
        ),
        {"m": match, "limit": page_size, "offset": offset},
    ).all()

    ids = [r.doc_id for r in rows]
    if not ids:
        return [], total

    docs = {d.id: d for d in Document.query.filter(Document.id.in_(ids)).all()}
    term_re = compile_terms(tokenize(raw_query))
    items = [
        {
            "document": docs[r.doc_id],
            "snippet": r.snip,
            "hit_count": _hit_count(docs[r.doc_id], term_re),
        }
        for r in rows
        if r.doc_id in docs
    ]
    return items, total
