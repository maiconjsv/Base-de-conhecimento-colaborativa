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


# --------------------------------------------------------------------------- #
# Cruzamento entre pesquisas (abas da tela "Pesquisas")
# --------------------------------------------------------------------------- #
CROSS_OPS = ("and", "or", "not")
MAX_CROSS_QUERIES = 8


def ranked_ids(raw_query: str) -> list[int]:
    """Todos os documentos que casam com a pesquisa, do mais ao menos relevante."""
    match = build_match_query(raw_query)
    if not match:
        return []
    rows = db.session.execute(
        text(
            """
            SELECT rowid FROM document_fts
            WHERE document_fts MATCH :m
            ORDER BY bm25(document_fts, 8.0, 4.0, 6.0, 1.0)
            """
        ),
        {"m": match},
    )
    return [r[0] for r in rows]


def _best_cross_snippet(snippets: list[str], regexes) -> str:
    """O trecho que reune termos de mais pesquisas diferentes (empate: o primeiro)."""
    best, best_n = "", -1
    for snip in snippets:
        plain = re.sub(r"<[^>]+>", "", snip)
        n = sum(1 for rx in regexes if rx is not None and rx.search(plain))
        if n > best_n:
            best, best_n = snip, n
    return best


def cross_documents(queries: list[str], op: str, *, base: int = 0, page: int = 1, page_size: int = 20):
    """Combina os resultados de varias pesquisas.

    op = "and": documentos presentes em TODAS as pesquisas;
         "or":  em QUALQUER uma (os que aparecem em mais pesquisas primeiro);
         "not": na pesquisa `base` e em NENHUMA das outras.

    Devolve (items, total). Cada item: {document, matches: [bool por pesquisa],
    hits: [ocorrencias por pesquisa], snippet}.
    """
    from .locator import find_snippets

    if op not in CROSS_OPS:
        raise ValueError(op)
    queries = queries[:MAX_CROSS_QUERIES]
    lists = [ranked_ids(q) for q in queries]
    sets = [set(ids) for ids in lists]
    # posicao no ranking de cada pesquisa (quem nao aparece fica no fim)
    pos = [{doc_id: i for i, doc_id in enumerate(ids)} for ids in lists]

    def rank_sum(doc_id):
        return sum(p.get(doc_id, len(p) + 1) for p in pos)

    if op == "and":
        ids = set.intersection(*sets) if sets else set()
        ordered = sorted(ids, key=rank_sum)
    elif op == "or":
        ids = set.union(*sets) if sets else set()
        ordered = sorted(ids, key=lambda d: (-sum(d in s for s in sets), rank_sum(d)))
    else:
        base = min(max(base, 0), len(sets) - 1) if sets else 0
        others = set().union(*(s for i, s in enumerate(sets) if i != base))
        ordered = [d for d in lists[base] if d not in others] if sets else []

    total = len(ordered)
    page = max(page, 1)
    chunk = ordered[(page - 1) * page_size: page * page_size]
    if not chunk:
        return [], total

    docs = {d.id: d for d in Document.query.filter(Document.id.in_(chunk)).all()}
    regexes = [compile_terms(tokenize(q)) for q in queries]
    all_re = compile_terms([t for q in queries for t in tokenize(q)])
    items = []
    for doc_id in chunk:
        doc = docs.get(doc_id)
        if doc is None:
            continue
        snippets, _ = find_snippets(doc.content or doc.description, all_re, max_hits=60)
        items.append(
            {
                "document": doc,
                "matches": [doc_id in s for s in sets],
                "hits": [_hit_count(doc, rx) for rx in regexes],
                "snippet": _best_cross_snippet(snippets, regexes),
            }
        )
    return items, total
