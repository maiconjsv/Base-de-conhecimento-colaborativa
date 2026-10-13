"""Localizador de ocorrencias.

Dado o texto de um documento e os termos buscados, acha TODAS as posicoes onde
os termos aparecem e devolve trechos curtos com <mark> em volta. Usado pelo
resultado expansivel da busca ("mostrar onde aparece em cada documento").

Casamento igual ao do indice FTS5 (`app/search.py`):
- por prefixo: "link" acha "Link003";
- sem acento: "pagamento" acha "pagaménto" e vice-versa;
- sem diferenciar maiuscula/minuscula.

Em vez de normalizar o texto inteiro (custoso e bagunca os indices), a propria
regex do termo e expandida para aceitar as variantes acentuadas. Assim rodamos
`finditer` direto no texto original e as posicoes batem.
"""

import re
import unicodedata
from html import escape

# Mesmo criterio de "caractere de palavra" do FTS: letra/numero, sem underscore.
_WORD = r"[^\W_]"
_WORD_RE = re.compile(_WORD, re.UNICODE)

# Letra base -> todas as formas acentuadas que devem casar com ela.
_ACCENTS = {
    "a": "aàáâãäåāăą",
    "c": "cçćĉċč",
    "d": "dďđ",
    "e": "eèéêëēĕėęě",
    "g": "gĝğġģ",
    "i": "iìíîïĩīĭįı",
    "l": "lĺļľŀł",
    "n": "nñńņňŉ",
    "o": "oòóôõöøōŏő",
    "r": "rŕŗř",
    "s": "sśŝşš",
    "t": "tţťŧ",
    "u": "uùúûüũūŭůűų",
    "y": "yýÿŷ",
    "z": "zźżž",
}


def _strip_diacritics(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c)
    )


def compile_terms(tokens):
    """Compila os termos numa regex unica (ou None se nao houver termo util)."""
    parts = []
    for tok in tokens:
        base = _strip_diacritics(tok).lower()
        if not base:
            continue
        chars = []
        for ch in base:
            if ch in _ACCENTS:
                chars.append("[" + _ACCENTS[ch] + "]")
            else:
                chars.append(re.escape(ch))
        # inicio de palavra + termo + resto da palavra (prefixo, igual ao FTS `tok*`)
        parts.append("(?<!" + _WORD + ")" + "".join(chars) + _WORD + "*")
    if not parts:
        return None
    return re.compile("|".join(parts), re.IGNORECASE | re.UNICODE)


def count_matches(text: str, term_re) -> int:
    if not text or term_re is None:
        return 0
    return sum(1 for _ in term_re.finditer(text))


def find_snippets(text, term_re, *, ctx=90, max_hits=200, join_gap=20):
    """(lista de HTML de trechos, total_de_ocorrencias).

    Os trechos ja vem escapados, com <mark>...</mark> nos termos. Ocorrencias
    proximas entram no mesmo trecho. Para em `max_hits` ocorrencias.
    """
    if not text or term_re is None:
        return [], 0

    spans = [(m.start(), m.end()) for m in term_re.finditer(text) if m.end() > m.start()]
    total = len(spans)
    if not spans:
        return [], 0

    n = len(text)
    windows = []  # [start, end, [(s, e), ...]]
    for s, e in spans[:max_hits]:
        ws, we = max(0, s - ctx), min(n, e + ctx)
        if windows and ws <= windows[-1][1] + join_gap:
            windows[-1][1] = max(windows[-1][1], we)
            windows[-1][2].append((s, e))
        else:
            windows.append([ws, we, [(s, e)]])

    return [render_window(text, ws, we, marks) for ws, we, marks in windows], total


def render_window(text, ws, we, marks):
    """HTML escapado de text[ws:we] com <mark> nos spans `marks` (ordenados).

    As bordas sao estendidas ate o fim da palavra para nao cortar no meio.
    """
    n = len(text)
    while ws > 0 and _WORD_RE.match(text[ws - 1]):
        ws -= 1
    while we < n and _WORD_RE.match(text[we]):
        we += 1

    buf, cur = [], ws
    for s, e in marks:
        if s < cur or e > we:
            continue
        buf.append(escape(text[cur:s]))
        buf.append("<mark>")
        buf.append(escape(text[s:e]))
        buf.append("</mark>")
        cur = e
    buf.append(escape(text[cur:we]))

    frag = re.sub(r"\s+", " ", "".join(buf)).strip()
    if ws > 0:
        frag = "… " + frag
    if we < n:
        frag = frag + " …"
    return frag
