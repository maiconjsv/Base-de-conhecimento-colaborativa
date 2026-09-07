"""Deriva automaticamente titulo, resumo e palavras-chave de um documento.

Ordem de preferencia para o TITULO:
1. Titulo embutido nos metadados do arquivo (PDF/DOCX/XLSX/PPTX).
2. Primeiro cabecalho Markdown (`# ...`) ou primeira linha "de titulo" do texto.
3. Nome do arquivo, higienizado.

RESUMO: assunto/descricao embutidos ou as primeiras frases do texto extraido.
PALAVRAS-CHAVE: termos mais frequentes do texto, sem palavras vazias (PT/EN).
"""

import re
import unicodedata
from collections import Counter
from pathlib import Path

MAX_TITLE_LEN = 160
SUMMARY_LEN = 320
MAX_KEYWORDS = 8

_WORD_RE = re.compile(r"[^\W\d_]{4,}", re.UNICODE)
_WS_RE = re.compile(r"\s+")

# Palavras vazias mais comuns em portugues e ingles.
_STOPWORDS = {
    # portugues
    "a", "o", "os", "as", "um", "uma", "uns", "umas", "de", "do", "da", "dos",
    "das", "em", "no", "na", "nos", "nas", "por", "para", "com", "sem", "sob",
    "sobre", "entre", "ate", "apos", "ante", "que", "quem", "qual", "quais",
    "quando", "onde", "como", "porque", "pois", "mas", "porem", "entao", "se",
    "nao", "sim", "ja", "ainda", "muito", "muita", "muitos", "muitas", "mais",
    "menos", "todo", "toda", "todos", "todas", "este", "esta", "estes", "estas",
    "esse", "essa", "esses", "essas", "isso", "isto", "aquele", "aquela", "seu",
    "sua", "seus", "suas", "meu", "minha", "nosso", "nossa", "dele", "dela",
    "ser", "estar", "ter", "haver", "fazer", "pode", "podem", "deve", "devem",
    "foi", "sao", "era", "eram", "sera", "serao", "cada", "outro", "outra",
    "outros", "outras", "tambem", "apenas", "conforme", "atraves", "assim",
    "dessa", "desse", "deste", "desta", "pela", "pelo", "pelos", "pelas",
    "numa", "num", "aos", "nem", "lhe", "lhes", "eles", "elas", "voce", "nos",
    # ingles
    "the", "and", "for", "are", "was", "were", "with", "that", "this", "from",
    "have", "has", "had", "not", "but", "you", "your", "our", "their", "they",
    "them", "there", "here", "what", "which", "when", "where", "will", "would",
    "should", "could", "can", "may", "shall", "into", "about", "over", "than",
    "then", "them", "some", "such", "only", "also", "each", "other", "more",
    "most", "been", "being", "these", "those",
}


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def humanize_filename(filename: str) -> str:
    stem = Path(filename).stem
    stem = re.sub(r"[_\-]+", " ", stem)
    stem = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", stem)  # camelCase -> palavras
    stem = _WS_RE.sub(" ", stem).strip()
    if not stem:
        return "Documento sem nome"
    return stem[0].upper() + stem[1:]


def _title_from_text(text: str) -> str:
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        heading = re.match(r"^#{1,6}\s+(.*)", line)  # Markdown
        if heading:
            line = heading.group(1).strip()
        line = line.strip("#*_=~-> \t")
        if len(line) < 3 or not re.search(r"[^\W\d_]", line):
            continue
        if len(line) > MAX_TITLE_LEN:
            line = line[:MAX_TITLE_LEN].rsplit(" ", 1)[0] + "…"
        return line
    return ""


def _summary_from_text(text: str) -> str:
    body = _WS_RE.sub(" ", text).strip()
    if not body:
        return ""
    if len(body) <= SUMMARY_LEN:
        return body
    cut = body[:SUMMARY_LEN]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:.") + "…"


def extract_keywords(text: str, limit: int = MAX_KEYWORDS) -> list[str]:
    counts: Counter[str] = Counter()
    display: dict[str, str] = {}
    for match in _WORD_RE.findall(text):
        key = _strip_accents(match).lower()
        if key in _STOPWORDS or len(key) < 4:
            continue
        counts[key] += 1
        display.setdefault(key, match.lower())
    # exige que o termo apareca ao menos 2x quando o texto e longo
    threshold = 2 if len(text) > 1200 else 1
    ranked = [k for k, n in counts.most_common(limit * 3) if n >= threshold]
    return [display[k] for k in ranked[:limit]]


def derive_metadata(*, original_filename: str, text: str, embedded: dict) -> dict:
    """Devolve {'title', 'description', 'tags'} prontos para gravar."""
    text = text or ""
    embedded = embedded or {}

    title = (
        (embedded.get("title") or "").strip()
        or _title_from_text(text)
        or humanize_filename(original_filename)
    )
    if len(title) > MAX_TITLE_LEN:
        title = title[:MAX_TITLE_LEN].rsplit(" ", 1)[0] + "…"

    description = (embedded.get("summary") or "").strip() or _summary_from_text(text)

    tags = ", ".join(extract_keywords(text))

    return {"title": title, "description": description, "tags": tags}
