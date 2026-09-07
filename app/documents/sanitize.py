"""Sanitizador de HTML por lista de permissao (sem dependencias externas).

Usado para exibir Markdown convertido em HTML com seguranca: remove qualquer
tag/atributo fora da lista e bloqueia URLs com esquemas perigosos.
"""

from html import escape
from html.parser import HTMLParser

_ALLOWED_TAGS = {
    "p", "br", "hr", "h1", "h2", "h3", "h4", "h5", "h6",
    "strong", "em", "b", "i", "u", "s", "del", "ins", "sup", "sub", "mark",
    "ul", "ol", "li", "blockquote", "pre", "code", "span",
    "table", "thead", "tbody", "tfoot", "tr", "th", "td",
    "a", "img",
}
_VOID_TAGS = {"br", "hr", "img"}
_ALLOWED_ATTRS = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title"},
    "th": {"align"},
    "td": {"align"},
}
_URL_ATTRS = {("a", "href"), ("img", "src")}
_SAFE_PREFIXES = ("http:", "https:", "mailto:", "tel:", "#", "/", "data:image/")


def _safe_url(value: str) -> bool:
    return value.strip().lower().startswith(_SAFE_PREFIXES)


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def _emit_start(self, tag: str, attrs, self_closing: bool) -> None:
        if tag not in _ALLOWED_TAGS:
            return
        allowed = _ALLOWED_ATTRS.get(tag, set())
        rendered = []
        for name, value in attrs:
            if name not in allowed:
                continue
            value = value or ""
            if (tag, name) in _URL_ATTRS and not _safe_url(value):
                continue
            rendered.append(f' {name}="{escape(value, quote=True)}"')
        slash = "/" if tag in _VOID_TAGS else ""
        self.parts.append(f"<{tag}{''.join(rendered)}{slash}>")

    def handle_starttag(self, tag, attrs):
        self._emit_start(tag, attrs, self_closing=False)

    def handle_startendtag(self, tag, attrs):
        self._emit_start(tag, attrs, self_closing=True)

    def handle_endtag(self, tag):
        if tag in _ALLOWED_TAGS and tag not in _VOID_TAGS:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        self.parts.append(escape(data))


def sanitize_html(html: str) -> str:
    parser = _Sanitizer()
    parser.feed(html or "")
    parser.close()
    return "".join(parser.parts)
