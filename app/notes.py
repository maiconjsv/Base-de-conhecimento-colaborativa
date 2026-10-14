"""Aqui vai o bloco de notas: painel lateral da moldura de abas (static/notes.js).

Cada usuario tem uma ou mais notas. Uma nota junta RECORTES trazidos das abas
(texto selecionado + fonte: titulo e endereco da pagina, para reabrir) e um
TEXTO LIVRE para cruzar os dados. Salvo no banco (entra no backup de dados\\).

API JSON (so do proprio usuario):
  GET    /notas/api              lista (cria "Minhas anotações" se nao houver)
  GET    /notas/api/<id>         nota completa
  POST   /notas/api              cria  {title}
  PUT    /notas/api/<id>         altera {title?, body?, clips?}
  DELETE /notas/api/<id>         apaga
  GET    /notas/<id>/exportar    texto (.txt) com recortes, fontes e anotacoes

As chamadas que alteram dados exigem o cabecalho X-KB-Notas: um site de fora
nao consegue envia-lo (o navegador bloqueia cabecalho proprio entre sites), o
que protege contra requisicoes forjadas sem precisar de token.
"""

import json
from datetime import datetime

from flask import Blueprint, Response, abort, jsonify, request, url_for
from flask_login import current_user, login_required

from .db import db
from .models import Note

bp = Blueprint("notes", __name__, url_prefix="/notas")

MAX_BODY = 200_000
MAX_CLIPS = 300
MAX_CLIP_TEXT = 5_000
MAX_TITLE = 120


def _guard():
    if request.method != "GET" and request.headers.get("X-KB-Notas") != "1":
        abort(400)


def _own(note_id: int) -> Note:
    note = db.session.get(Note, note_id)
    if note is None or note.user_id != current_user.id:
        abort(404)
    return note


def _summary(n: Note) -> dict:
    return {"id": n.id, "title": n.title, "clips": len(n.clip_list),
            "updated_at": n.updated_at.isoformat(timespec="seconds")}


def _full(n: Note) -> dict:
    return {**_summary(n), "body": n.body, "clips": n.clip_list,
            "export_url": url_for("notes.export", note_id=n.id)}


def _clean_clips(raw) -> list[dict]:
    if not isinstance(raw, list):
        abort(400)
    out = []
    for c in raw[:MAX_CLIPS]:
        if not isinstance(c, dict) or not isinstance(c.get("text"), str):
            continue
        url = c.get("url") if isinstance(c.get("url"), str) else ""
        if not url.startswith("/") or url.startswith("//"):
            url = ""                      # so caminhos do proprio sistema
        out.append({
            "text": c["text"][:MAX_CLIP_TEXT],
            "title": str(c.get("title") or "")[:200],
            "url": url[:500],
            "at": str(c.get("at") or "")[:25],
        })
    return out


@bp.before_request
@login_required
def _before():
    _guard()


@bp.get("/api")
def list_notes():
    notes = Note.query.filter_by(user_id=current_user.id).order_by(Note.updated_at.desc()).all()
    if not notes:
        n = Note(user_id=current_user.id, title="Minhas anotações")
        db.session.add(n)
        db.session.commit()
        notes = [n]
    return jsonify([_summary(n) for n in notes])


@bp.get("/api/<int:note_id>")
def get_note(note_id: int):
    return jsonify(_full(_own(note_id)))


@bp.post("/api")
def create_note():
    data = request.get_json(silent=True) or {}
    title = str(data.get("title") or "").strip()[:MAX_TITLE] or "Nova nota"
    n = Note(user_id=current_user.id, title=title)
    db.session.add(n)
    db.session.commit()
    return jsonify(_full(n)), 201


@bp.put("/api/<int:note_id>")
def update_note(note_id: int):
    n = _own(note_id)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400)
    if "title" in data:
        n.title = str(data["title"] or "").strip()[:MAX_TITLE] or n.title
    if "body" in data:
        if not isinstance(data["body"], str):
            abort(400)
        n.body = data["body"][:MAX_BODY]
    if "clips" in data:
        n.clips = json.dumps(_clean_clips(data["clips"]), ensure_ascii=False)
    n.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(_summary(n))


@bp.delete("/api/<int:note_id>")
def delete_note(note_id: int):
    db.session.delete(_own(note_id))
    db.session.commit()
    return jsonify({"ok": True})


@bp.get("/<int:note_id>/exportar")
def export(note_id: int):
    n = _own(note_id)
    lines = [n.title, "=" * len(n.title), ""]
    clips = n.clip_list
    if clips:
        lines.append("RECORTES")
        for i, c in enumerate(clips, 1):
            lines.append(f"[{i}] {c['text'].strip()}")
            src = c.get("title") or ""
            if c.get("url"):
                src = f"{src} ({request.host_url.rstrip('/')}{c['url']})" if src else c["url"]
            if src:
                lines.append(f"    fonte: {src}")
            lines.append("")
    if n.body.strip():
        lines += ["ANOTAÇÕES", n.body.strip(), ""]
    filename = "".join(ch if ch.isalnum() or ch in " -_" else "_" for ch in n.title).strip() or "notas"
    return Response(
        "\n".join(lines),
        mimetype="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}.txt"'},
    )
