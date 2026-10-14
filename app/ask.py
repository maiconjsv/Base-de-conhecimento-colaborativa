"""Assistente de perguntas, sem IA: responde com os trechos mais relevantes.

Fluxo de `answer(pergunta)`:
1. `extract_terms`: tira palavras vazias ("como", "faço", "o que"...) e reduz
   cada palavra a um radical simples (plural, -ção, -ado, verbos), que casa por
   prefixo: "senhas" -> "senh" acha "senha", "senhas"; "configuração" ->
   "configura" acha "configurar", "configurado".
2. Candidatos: FTS5 com OR entre os radicais (basta mencionar um termo).
   Peso de cada termo = idf (termo raro vale mais que termo que esta em tudo).
3. Para os melhores candidatos, varre o texto e pontua janelas de ~350
   caracteres: soma idf x frequencia (saturada), multiplicada pela cobertura
   (quanto do peso total da pergunta aparece junto) e pela proximidade.
4. As melhores janelas viram a resposta; todos os documentos que mencionam
   algum termo vem listados, os que tem todos os termos primeiro.
"""

import json
import math
import re
import unicodedata

from sqlalchemy import text

from .db import db
from .documents.analyze import _STOPWORDS
from .locator import compile_terms, render_window
from .models import Document, SheetRow
from .search import tokenize
from .sheets import match_rows, render_row_groups

MAX_TERMS = 10
MAX_DOCS_LISTED = 100
DOCS_SCANNED = 40          # quantos documentos tem o texto varrido atras de trechos
MAX_PASSAGES = 6
PASSAGES_PER_DOC = 2
MIN_RELATIVE_SCORE = 0.2   # descarta trechos com menos de 20% da nota do melhor
WINDOW = 350               # largura (caracteres) da janela que agrupa ocorrencias
SNIPPET_LEN = 420          # tamanho alvo do trecho mostrado
MAX_HITS_PER_TERM = 400    # por documento, para nao travar em textos enormes
ROWS_PER_TABLE = 5         # linhas de planilha mostradas num trecho
ROW_RELATIVE_SCORE = 0.5   # linha com menos da metade da nota da melhor fica de fora
CONTEXT_WEIGHT = 0.6       # termo no cabecalho/nome da aba vale 60% de um termo na celula

# Palavras de pergunta/conversa que nao ajudam a achar nada.
_QUESTION_WORDS = {
    "como", "faco", "faz", "fazer", "qual", "quais", "quero", "queria", "gostaria",
    "preciso", "precisa", "precisamos", "saber", "existe", "existem", "tem", "tenho",
    "temos", "algum", "alguma", "alguns", "algumas", "alguem", "sobre", "oque",
    "porque", "pq", "pra", "pro", "pras", "pros", "me", "eu", "vc", "voces", "ajuda",
    "ajudar", "favor", "consigo", "posso", "podemos", "devo", "e", "eh", "ou",
    "esta", "estao", "isso", "aqui", "ali", "la", "fica", "ficam", "encontro",
    "encontrar", "acho", "achar", "informacao", "informacoes", "explique", "explica",
    "mostre", "mostra", "diga", "fale", "ola", "bom", "dia", "tarde", "noite",  # "oi" fica: e a operadora
    "obrigado", "obrigada", "how", "do", "does", "is", "to", "of", "in", "on", "a",
    "an", "i", "we", "it", "or", "be", "who", "why", "find", "show", "me", "tell",
}
_IGNORE = _STOPWORDS | _QUESTION_WORDS

# Sufixos removidos (texto sem acento), do mais longo ao mais curto. So corta se
# sobrarem >= 4 letras, para nao virar um prefixo que casa com tudo.
_SUFFIXES = (
    "amentos", "imentos", "amento", "imento", "idades", "idade", "acoes", "icoes",
    "mente", "ismos", "istas", "coes", "soes", "ismo", "ista", "ando", "endo",
    "indo", "aram", "eram", "iram", "ados", "idos", "adas", "idas", "cao", "sao",
    "ado", "ido", "ada", "ida", "oes", "aes", "ais", "ar", "er", "ir", "es", "s",
)
_MIN_STEM = 4


def _fold(word: str) -> str:
    """minusculo e sem acento."""
    return "".join(
        c for c in unicodedata.normalize("NFD", word.lower()) if not unicodedata.combining(c)
    )


def stem(word: str) -> str:
    base = _fold(word)
    # codigos, numeros e siglas curtas ficam como estao
    if any(c.isdigit() for c in base) or len(base) <= _MIN_STEM:
        return base
    if word.isupper() and len(word) <= 6:
        return base
    for suf in _SUFFIXES:
        if base.endswith(suf) and len(base) - len(suf) >= _MIN_STEM:
            return base[: -len(suf)]
    return base


def extract_terms(question: str) -> list[dict]:
    """[{'word': palavra original, 'stem': radical}], sem repeticao.

    Se a pergunta for so de palavras vazias, usa as palavras como vieram.
    """
    tokens = tokenize(question)
    kept = [t for t in tokens if _fold(t) not in _IGNORE and (len(t) > 1 or t.isdigit())]
    if not kept:
        kept = [t for t in tokens if len(t) > 1]

    terms: list[dict] = []
    for tok in kept:
        st = stem(tok)
        if not st:
            continue
        # "acess" ja cobre "acesso": nao conta o mesmo termo duas vezes
        if any(st.startswith(t["stem"]) for t in terms):
            continue
        terms = [t for t in terms if not t["stem"].startswith(st)]
        terms.append({"word": tok, "stem": st})
        if len(terms) >= MAX_TERMS:
            break
    return terms


def _fts_term(st: str) -> str:
    return f'"{st}"*'


def _docs_with_term(st: str) -> set[int]:
    rows = db.session.execute(
        text("SELECT rowid FROM document_fts WHERE document_fts MATCH :m"),
        {"m": _fts_term(st)},
    )
    return {r[0] for r in rows}


def _ranked_candidates(stems: list[str]) -> list[int]:
    rows = db.session.execute(
        text(
            """
            SELECT rowid FROM document_fts
            WHERE document_fts MATCH :m
            ORDER BY bm25(document_fts, 8.0, 4.0, 6.0, 1.0)
            """
        ),
        {"m": " OR ".join(_fts_term(s) for s in stems)},
    )
    return [r[0] for r in rows]


def _idf(total_docs: int, df: int) -> float:
    return math.log(1 + (total_docs - df + 0.5) / (df + 0.5))


def _snap_start(content: str, pos: int, limit: int = 140) -> int:
    """Recua ate o comeco da frase/linha, se estiver perto."""
    lo = max(0, pos - limit)
    cut = max(content.rfind(". ", lo, pos), content.rfind("\n", lo, pos))
    if cut >= 0:
        return cut + 1
    return pos


def _snap_end(content: str, pos: int, limit: int = 140) -> int:
    """Avanca ate o fim da frase/linha, se estiver perto."""
    hi = min(len(content), pos + limit)
    cands = [i for i in (content.find(". ", pos, hi), content.find("\n", pos, hi)) if i >= 0]
    if cands:
        return min(cands) + 1
    return pos


def _best_windows(content: str, regexes, weights: list[float]):
    """Melhores janelas de um texto: [(score, start, end, set(termos))]."""
    hits = []
    for ti, rx in enumerate(regexes):
        for k, m in enumerate(rx.finditer(content)):
            if k >= MAX_HITS_PER_TERM:
                break
            if m.end() > m.start():
                hits.append((m.start(), m.end(), ti))
    if not hits:
        return [], hits
    hits.sort()

    total_w = sum(weights) or 1.0
    scored = []
    j = 0
    counts: dict[int, int] = {}
    for i in range(len(hits)):
        # janela deslizante: hits[i..j) cabem em WINDOW caracteres
        if i > 0:
            prev = hits[i - 1][2]
            counts[prev] -= 1
            if not counts[prev]:
                del counts[prev]
        j = max(j, i)
        while j < len(hits) and hits[j][0] - hits[i][0] <= WINDOW:
            counts[hits[j][2]] = counts.get(hits[j][2], 0) + 1
            j += 1

        base = sum(weights[t] * (1 + math.log(c)) for t, c in counts.items())
        coverage = sum(weights[t] for t in counts) / total_w
        span = hits[j - 1][1] - hits[i][0]
        closeness = 1 + 0.5 * (1 - min(span, WINDOW) / WINDOW) if len(counts) > 1 else 1
        score = base * (1 + 2 * coverage**2) * closeness
        scored.append((score, hits[i][0], hits[j - 1][1], frozenset(counts)))

    # escolhe as melhores sem sobreposicao
    scored.sort(key=lambda s: s[0], reverse=True)
    chosen = []
    for score, s, e, terms in scored:
        if any(s < ce + 80 and e > cs - 80 for _, cs, ce, _ in chosen):
            continue
        chosen.append((score, s, e, terms))
        if len(chosen) >= PASSAGES_PER_DOC:
            break
    return chosen, hits


def _render_passage(content: str, s: int, e: int, hits) -> str:
    pad = max(60, (SNIPPET_LEN - (e - s)) // 2)
    ws = _snap_start(content, max(0, s - pad))
    we = _snap_end(content, min(len(content), e + pad))
    marks = [(hs, he) for hs, he, _ in hits if hs >= ws and he <= we]
    return render_window(content, ws, we, marks)


AI_CONTEXT_PAD = 280   # texto ao redor do trecho enviado a IA (um pouco mais que o mostrado)


def _plain_passage(content: str, s: int, e: int) -> str:
    """Texto puro do trecho, mais largo que o exibido, para a IA ter contexto."""
    ws = _snap_start(content, max(0, s - AI_CONTEXT_PAD))
    we = _snap_end(content, min(len(content), e + AI_CONTEXT_PAD))
    return re.sub(r"\s+", " ", content[ws:we]).strip()


def _plain_rows(doc, rows) -> str:
    """Linhas de planilha como texto "Coluna: valor", com aba e linha (para a IA)."""
    from .sheets import column_letter

    sheets = {s.id: s for s in doc.sheets}
    lines = []
    for r in rows:
        sheet = sheets.get(r.sheet_id)
        if sheet is None:
            continue
        header = sheet.header_list
        cells = json.loads(r.cells)
        pairs = [
            f"{(header[i] if i < len(header) and header[i] else column_letter(sheet.col_offset + i))}: {v}"
            for i, v in enumerate(cells) if v
        ]
        lines.append(f"aba {sheet.name}, linha {r.row_number}: " + "; ".join(pairs))
    return "\n".join(lines)


def _best_rows(doc, regexes, weights, fts_query: str):
    """Melhores linhas de uma planilha: (score, linhas, termos da melhor).

    Termo que casa com o cabecalho ou o nome da aba conta para todas as linhas
    daquela aba ("qual o IP do servidor da VPN?": "IP" e a coluna, "servidor" a
    aba, e a linha que cita "vpn" e a resposta), com peso menor que o da celula.
    """
    total_w = sum(weights) or 1.0
    context = {}  # sheet_id -> termos no cabecalho / nome da aba
    for sheet in doc.sheets:
        label = sheet.name + " " + " ".join(sheet.header_list)
        context[sheet.id] = {t for t, rx in enumerate(regexes) if rx.search(label)}

    def score_of(own: dict, ctx: set):
        ctx = ctx - set(own)
        base = sum(weights[t] * (1 + math.log(c)) for t, c in own.items())
        base += CONTEXT_WEIGHT * sum(weights[t] for t in ctx)
        covered = frozenset(own) | ctx
        coverage = sum(weights[t] for t in covered) / total_w
        return base * (1 + 2 * coverage**2), covered

    scored = []
    for row in match_rows(doc.id, fts_query):
        counts = {t: len(rx.findall(row.text)) for t, rx in enumerate(regexes)}
        counts = {t: c for t, c in counts.items() if c}
        if not counts:
            continue
        score, covered = score_of(counts, context.get(row.sheet_id, set()))
        scored.append((score, covered, row))

    if not scored:
        # nenhuma celula cita os termos, mas o cabecalho sim: mostra o comeco da aba
        best = max(doc.sheets, key=lambda s: sum(weights[t] for t in context[s.id]), default=None)
        if best is None or not context[best.id]:
            return 0.0, [], frozenset()
        score, covered = score_of({}, context[best.id])
        rows = (
            SheetRow.query.filter_by(sheet_id=best.id)
            .order_by(SheetRow.row_number)
            .limit(ROWS_PER_TABLE)
            .all()
        )
        return score, rows, covered
    scored.sort(key=lambda s: s[0], reverse=True)
    floor = scored[0][0] * ROW_RELATIVE_SCORE
    top = [s for s in scored if s[0] >= floor][:ROWS_PER_TABLE]
    rows = sorted((s[2] for s in top), key=lambda r: (r.sheet_id, r.row_number))
    return top[0][0], rows, top[0][1]


def answer(question: str, url_for_doc) -> dict:
    """Monta a resposta (dict serializavel em JSON).

    `url_for_doc(doc_id)` devolve o link do documento (injetado pela rota).
    """
    terms = extract_terms(question)
    result = {
        "query": question,
        "terms": [],
        "missing": [],
        "status": "empty",
        "passages": [],
        "documents": [],
        "total_documents": 0,
        "hits_q": " ".join(t["stem"] for t in terms),
    }
    if not terms:
        return result

    total_docs = db.session.query(Document.id).count()
    per_term = [_docs_with_term(t["stem"]) for t in terms]
    for t, docs in zip(terms, per_term):
        result["terms"].append({"word": t["word"], "stem": t["stem"], "docs": len(docs)})
    result["missing"] = [t["word"] for t, docs in zip(terms, per_term) if not docs]

    # so os termos que existem em algum lugar participam da busca
    live = [i for i, docs in enumerate(per_term) if docs]
    if not live:
        result["status"] = "none"
        return result

    live_terms = [terms[i] for i in live]
    live_sets = [per_term[i] for i in live]
    weights = [_idf(total_docs, len(s)) for s in live_sets]
    total_w = sum(weights) or 1.0
    regexes = [compile_terms([t["stem"]]) for t in live_terms]

    ranked = _ranked_candidates([t["stem"] for t in live_terms])
    bm25_pos = {doc_id: pos for pos, doc_id in enumerate(ranked)}
    result["total_documents"] = len(ranked)

    # ordem da lista: mais peso de termos coberto primeiro, depois bm25
    def doc_terms(doc_id):
        return [k for k, s in enumerate(live_sets) if doc_id in s]

    def list_key(doc_id):
        covered = sum(weights[k] for k in doc_terms(doc_id))
        return (-covered, bm25_pos[doc_id])

    listed_ids = sorted(ranked, key=list_key)[:MAX_DOCS_LISTED]
    scan_ids = listed_ids[:DOCS_SCANNED]
    docs = {
        d.id: d
        for d in Document.query.filter(Document.id.in_(listed_ids)).all()
    }

    or_query = " OR ".join(_fts_term(t["stem"]) for t in live_terms)
    any_re = compile_terms([t["stem"] for t in live_terms])
    passages = []
    for doc_id in scan_ids:
        doc = docs.get(doc_id)
        if doc is None or not doc.content:
            continue
        # termo no titulo/tags reforca o documento todo
        meta = f"{doc.title}\n{doc.tags}"
        meta_bonus = 1 + 0.15 * sum(1 for rx in regexes if rx.search(meta))

        if doc.sheets:
            # planilha: o "trecho" sao as linhas mais relevantes, com aba e linha
            score, rows, covered = _best_rows(doc, regexes, weights, or_query)
            if rows:
                passages.append(
                    {
                        "kind": "table",
                        "score": score * meta_bonus,
                        "doc_id": doc.id,
                        "title": doc.title,
                        "filename": doc.original_filename,
                        "url": url_for_doc(doc.id),
                        "html": render_row_groups(
                            doc, [(r.sheet_id, r.row_number, r.cells) for r in rows], any_re
                        ),
                        "label": f"Planilha “{doc.title}” ({doc.original_filename})",
                        "plain": _plain_rows(doc, rows),
                        "covered": [live_terms[k]["word"] for k in sorted(covered)],
                        "complete": len(covered) == len(live_terms),
                        "coverage": sum(weights[k] for k in covered) / total_w,
                    }
                )
            continue

        chosen, hits = _best_windows(doc.content, regexes, weights)
        for score, s, e, covered in chosen:
            passages.append(
                {
                    "kind": "text",
                    "score": score * meta_bonus,
                    "doc_id": doc.id,
                    "title": doc.title,
                    "filename": doc.original_filename,
                    "url": url_for_doc(doc.id),
                    "html": _render_passage(doc.content, s, e, hits),
                    "label": f"Documento “{doc.title}” ({doc.original_filename})",
                    "plain": _plain_passage(doc.content, s, e),
                    "covered": [live_terms[k]["word"] for k in sorted(covered)],
                    "complete": len(covered) == len(live_terms),
                    "coverage": sum(weights[k] for k in covered) / total_w,
                }
            )

    passages.sort(key=lambda p: p["score"], reverse=True)
    if passages:
        # trecho muito mais fraco que o melhor so polui a resposta
        floor = passages[0]["score"] * MIN_RELATIVE_SCORE
        passages = [p for p in passages if p["score"] >= floor]
    result["passages"] = passages[:MAX_PASSAGES]
    for p in result["passages"]:
        p["score"] = round(p["score"], 2)
        p["coverage"] = round(p["coverage"], 2)

    for doc_id in listed_ids:
        doc = docs.get(doc_id)
        if doc is None:
            continue
        has = doc_terms(doc_id)
        result["documents"].append(
            {
                "doc_id": doc.id,
                "title": doc.title,
                "filename": doc.original_filename,
                "date": doc.uploaded_at.strftime("%d/%m/%Y"),
                "url": url_for_doc(doc.id),
                "terms": [live_terms[k]["word"] for k in has],
                "complete": len(has) == len(live_terms),
            }
        )

    if result["passages"] and result["passages"][0]["complete"] and not result["missing"]:
        result["status"] = "full"
    else:
        result["status"] = "partial"
    return result


def suggested_topics(limit: int = 8) -> list[str]:
    """Tags mais comuns na base, para sugerir por onde comecar."""
    counts: dict[str, int] = {}
    shown: dict[str, str] = {}
    for (tags,) in db.session.query(Document.tags).all():
        for tag in (tags or "").split(","):
            tag = tag.strip()
            if not tag:
                continue
            key = _fold(tag)
            counts[key] = counts.get(key, 0) + 1
            shown.setdefault(key, tag)
    ranked = sorted(counts, key=lambda k: (-counts[k], k))
    return [shown[k] for k in ranked[:limit]]
