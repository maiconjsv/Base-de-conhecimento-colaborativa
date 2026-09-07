"""Decide como pre-visualizar um documento dentro do sistema (sem baixar)."""

import csv
import io

import markdown as md_lib
from markupsafe import Markup

from .sanitize import sanitize_html

# tipos de visualizacao
PDF = "pdf"
MARKDOWN = "markdown"
CSV = "csv"
TEXT = "text"
TEXT_ONLY = "text_only"  # office: so a previa de texto extraido

_MD_EXTENSIONS = ["fenced_code", "tables", "sane_lists", "nl2br"]
_CSV_MAX_ROWS = 300


def preview_kind(ext: str) -> str:
    ext = (ext or "").lower().lstrip(".")
    if ext == "pdf":
        return PDF
    if ext in ("md", "markdown"):
        return MARKDOWN
    if ext == "csv":
        return CSV
    if ext == "txt":
        return TEXT
    return TEXT_ONLY


def render_markdown(text: str) -> Markup:
    html = md_lib.markdown(text or "", extensions=_MD_EXTENSIONS, output_format="html")
    return Markup(sanitize_html(html))


def render_csv(text: str):
    """Devolve (linhas, truncado). Cada linha e uma lista de strings (o template escapa)."""
    rows = []
    try:
        reader = csv.reader(io.StringIO(text or ""))
        for i, row in enumerate(reader):
            if i >= _CSV_MAX_ROWS:
                return rows, True
            rows.append(row)
    except csv.Error:
        return [], False
    return rows, False
