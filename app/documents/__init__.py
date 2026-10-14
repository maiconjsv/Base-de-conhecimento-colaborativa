import json

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    stream_with_context,
    url_for,
)
from flask_login import current_user, login_required

from .. import ask as ask_mod
from .. import llm
from ..db import db
from ..dedup import DuplicateDocument
from ..locator import compile_terms, find_snippets
from ..models import Document, DocumentImage
from ..search import CROSS_OPS, cross_documents, search_documents, tokenize
from ..sheets import match_rows, render_row_groups, sheet_page
from . import preview as preview_mod
from .forms import DeleteForm, EditForm, UploadForm
from .service import delete_document, ingest_file

bp = Blueprint("documents", __name__)


def _ext_of(name: str) -> str:
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


@bp.route("/")
@login_required
def shell():
    """Moldura com abas de navegador: cada aba e uma pagina do sistema (iframe)."""
    return render_template("shell.html")


@bp.route("/inicio")
@login_required
def index():
    recent = (
        Document.query.order_by(Document.uploaded_at.desc()).limit(20).all()
    )
    total = db.session.query(Document.id).count()
    return render_template("index.html", documents=recent, total=total)


@bp.route("/search")
@login_required
def search():
    query = request.args.get("q", "", type=str).strip()
    page = request.args.get("page", 1, type=int)
    page_size = current_app.config["PAGE_SIZE"]

    items, total = search_documents(query, page=page, page_size=page_size)
    pages = (total + page_size - 1) // page_size if total else 0

    return render_template(
        "search.html",
        query=query,
        items=items,
        total=total,
        page=page,
        pages=pages,
    )


_HIT_FIELDS = (
    ("Título", "title"),
    ("Resumo", "description"),
    ("Tags", "tags"),
    ("Conteúdo", "content"),
)
_HITS_PER_FIELD = 200


@bp.route("/search/hits/<int:doc_id>")
@login_required
def search_hits(doc_id: int):
    """Todas as ocorrencias dos termos dentro de um documento (JSON).

    Chamado por fetch() quando o usuario expande um resultado da busca.
    """
    doc = db.get_or_404(Document, doc_id)
    tokens = tokenize(request.args.get("q", ""))
    term_re = compile_terms(tokens)
    is_sheet = bool(doc.sheets)

    groups, count, tables_html, row_count = [], 0, "", 0
    if term_re is not None and is_sheet:
        # planilha: mostra as linhas (com aba e numero da linha) em vez do texto corrido
        rows = match_rows(doc.id, " OR ".join(f'"{t}"*' for t in tokens))
        row_count = len(rows)
        count += row_count
        tables_html = render_row_groups(doc, rows, term_re, filter_q=request.args.get("q", ""))
    if term_re is not None:
        for label, attr in _HIT_FIELDS:
            # planilha: o resumo e as tags sao derivados das linhas, so repetiriam
            if is_sheet and attr in ("content", "description", "tags"):
                continue
            snippets, found = find_snippets(
                getattr(doc, attr) or "", term_re, max_hits=_HITS_PER_FIELD
            )
            count += found
            if snippets:
                groups.append(
                    {"label": label, "snippets": snippets, "shown": len(snippets), "total": found}
                )

    return jsonify(
        {
            "doc_id": doc.id,
            "title": doc.title,
            "count": count,
            "groups": groups,
            "tables_html": tables_html,
            "row_count": row_count,
            "extraction_ok": doc.extraction_ok,
        }
    )


_WORKSPACE_PAGE_SIZE = 20


def _doc_json(doc: Document) -> dict:
    return {
        "doc_id": doc.id,
        "title": doc.title,
        "filename": doc.original_filename,
        "date": doc.uploaded_at.strftime("%d/%m/%Y"),
        "tags": doc.tag_list,
        "url": url_for("documents.detail", doc_id=doc.id),
    }


@bp.route("/pesquisas")
@login_required
def workspace():
    """Varias pesquisas em abas, com cruzamento entre elas (tudo via fetch)."""
    return render_template("workspace.html", add=request.args.get("q", "", type=str).strip())


@bp.route("/pesquisas/api")
@login_required
def workspace_search():
    query = request.args.get("q", "", type=str).strip()[:300]
    page = request.args.get("page", 1, type=int)
    items, total = search_documents(query, page=page, page_size=_WORKSPACE_PAGE_SIZE)
    return jsonify(
        {
            "query": query,
            "total": total,
            "page": page,
            "pages": (total + _WORKSPACE_PAGE_SIZE - 1) // _WORKSPACE_PAGE_SIZE,
            "items": [
                {**_doc_json(i["document"]), "snippet": i["snippet"], "hit_count": i["hit_count"]}
                for i in items
            ],
        }
    )


@bp.route("/pesquisas/cruzar")
@login_required
def workspace_cross():
    queries = [q.strip()[:300] for q in request.args.getlist("q") if q.strip()]
    op = request.args.get("op", "and", type=str)
    if op not in CROSS_OPS or len(queries) < 2:
        return jsonify({"error": "Escolha ao menos duas pesquisas e uma operação."}), 400
    page = request.args.get("page", 1, type=int)
    items, total = cross_documents(
        queries,
        op,
        base=request.args.get("base", 0, type=int),
        page=page,
        page_size=_WORKSPACE_PAGE_SIZE,
    )
    return jsonify(
        {
            "queries": queries,
            "op": op,
            "total": total,
            "page": page,
            "pages": (total + _WORKSPACE_PAGE_SIZE - 1) // _WORKSPACE_PAGE_SIZE,
            "items": [
                {
                    **_doc_json(i["document"]),
                    "snippet": i["snippet"],
                    "matches": i["matches"],
                    "hits": i["hits"],
                }
                for i in items
            ],
        }
    )


@bp.route("/contribuir")
def contribute():
    """Passo a passo para sugerir/contribuir com features. Publica (sem login)."""
    return render_template("contribute.html")


@bp.route("/perguntar")
@login_required
def ask():
    """Assistente: pergunta em linguagem natural -> trechos dos documentos."""
    return render_template(
        "ask.html",
        initial=request.args.get("q", "", type=str).strip(),
        topics=ask_mod.suggested_topics(),
    )


@bp.route("/perguntar/api")
@login_required
def ask_api():
    question = request.args.get("q", "", type=str).strip()[:500]
    return jsonify(
        ask_mod.answer(question, lambda doc_id: url_for("documents.detail", doc_id=doc_id))
    )


def _chat_history(raw: str) -> list[dict]:
    """Ultimas perguntas/respostas da conversa (enviadas pela pagina), saneadas."""
    try:
        items = json.loads(raw) if raw else []
    except ValueError:
        return []
    out = []
    for it in items[-llm.HISTORY_TURNS:] if isinstance(items, list) else []:
        if isinstance(it, dict) and isinstance(it.get("q"), str) and isinstance(it.get("a"), str):
            out.append({"q": it["q"][:500], "a": it["a"][: llm.HISTORY_ANSWER_CHARS]})
    return out


@bp.route("/perguntar/ia/status")
@login_required
def ask_ai_status():
    """IA local disponivel? (motor + modelo presentes, memoria da maquina)."""
    return jsonify(llm.engine.status())


@bp.route("/perguntar/ia")
@login_required
def ask_ai():
    """Resposta da IA local em streaming (NDJSON, uma linha JSON por evento).

    Eventos: meta (resultado da busca: trechos, documentos), status (texto de
    progresso), delta (pedaco da resposta), error, done. A busca roda antes do
    streaming; a IA so recebe a pergunta e os trechos encontrados.
    """
    question = request.args.get("q", "", type=str).strip()[:500]
    history = _chat_history(request.args.get("ctx", ""))
    to_url = lambda doc_id: url_for("documents.detail", doc_id=doc_id)  # noqa: E731
    short = len(ask_mod.extract_terms(question)) <= 2
    if history and short:
        # continuacao curta ("e o email?"): busca junto com a pergunta anterior,
        # senao "email" traria a linha de todo mundo
        result = ask_mod.answer(f"{history[-1]['q']} {question}", to_url)
        result["query"] = question
    else:
        result = ask_mod.answer(question, to_url)
        if not result["passages"] and history:
            result = ask_mod.answer(f"{history[-1]['q']} {question}", to_url)
            result["query"] = question
    passages = result["passages"]
    # o texto puro dos trechos so vai para a IA, nao para a pagina
    meta = {**result, "passages": [{k: v for k, v in p.items() if k != "plain"} for p in passages]}
    messages = llm.build_messages(question, passages, history) if passages else None

    def line(obj) -> str:
        return json.dumps(obj, ensure_ascii=False) + "\n"

    def events():
        yield line({"type": "meta", "result": meta})
        if not messages:
            yield line({"type": "done"})
            return
        try:
            if not llm.engine.running:
                yield line({"type": "status", "text": "Ligando a IA local… a primeira pergunta "
                                                      "demora alguns segundos enquanto o modelo carrega."})
                llm.engine.ensure_running()
            yield line({"type": "status", "text": "Lendo os trechos e escrevendo a resposta…"})
            for piece in llm.engine.stream_chat(messages):
                yield line({"type": "delta", "text": piece})
            yield line({"type": "done"})
        except llm.LLMError as exc:
            yield line({"type": "error", "text": str(exc)})

    return Response(
        stream_with_context(events()),
        mimetype="application/x-ndjson",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


def _skipped_message(skipped) -> str:
    """Aviso dos envios ignorados por ja existirem na base."""
    parts = []
    for name, dup in skipped:
        how = "arquivo idêntico a" if dup.reason == "arquivo" else "mesmo conteúdo de"
        parts.append(f"{name} ({how} “{dup.existing.title}”)")
    label = "Ignorado por já existir na base" if len(parts) == 1 else (
        f"{len(parts)} arquivos ignorados por já existirem na base"
    )
    return f"{label}: " + "; ".join(parts) + "."


def _upload_context(form):
    limit = current_app.config.get("MAX_CONTENT_LENGTH") or 0
    return {"form": form, "max_bytes": limit, "max_mb": limit // (1024 * 1024)}


@bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    form = UploadForm()
    if form.validate_on_submit():
        uploads = [f for f in form.files.data if f and f.filename]
        docs, failed, skipped = [], [], []
        for file_storage in uploads:
            try:
                docs.append(ingest_file(file_storage, user_id=current_user.id))
            except DuplicateDocument as dup:
                db.session.rollback()
                skipped.append((file_storage.filename or "arquivo", dup))
            except Exception:  # noqa: BLE001 - um arquivo ruim nao derruba o lote
                db.session.rollback()
                current_app.logger.exception(
                    "Falha ao processar upload %r", file_storage.filename
                )
                failed.append(file_storage.filename or "arquivo")

        if skipped:
            flash(_skipped_message(skipped), "info")
        if not docs and skipped and not failed:
            # tudo era duplicado: leva ao documento que ja existia (ou a lista)
            if len(skipped) == 1:
                return redirect(url_for("documents.detail", doc_id=skipped[0][1].existing.id))
            return redirect(url_for("documents.index"))

        if not docs:
            flash(
                "Não foi possível processar: " + ", ".join(failed)
                + ". Verifique se o arquivo não está corrompido ou protegido por senha.",
                "danger",
            )
            return render_template("upload.html", **_upload_context(form)), 422

        csvs = [d for d in docs if d.original_filename.lower().endswith(".csv")]
        if csvs:
            # CSV exportado do Excel leva so a aba que estava aberta
            flash(
                ("“" + csvs[0].original_filename + "” é CSV" if len(csvs) == 1
                 else f"{len(csvs)} arquivos são CSV")
                + ": esse formato guarda só uma aba. Se a planilha original tem várias "
                "abas, envie o arquivo do Excel (.xlsx) para todas entrarem na busca.",
                "info",
            )
        without_text = [d for d in docs if not d.extraction_ok]
        if failed:
            flash("Falha ao processar: " + ", ".join(failed), "warning")

        if len(docs) == 1 and not failed:
            doc = docs[0]
            if doc.extraction_ok:
                flash(
                    f"“{doc.title}” foi indexado. Confira as informações extraídas.",
                    "success",
                )
            else:
                flash(
                    f"“{doc.title}” foi salvo, mas não foi possível ler o texto do "
                    "arquivo. A busca vai considerar só o título e as tags.",
                    "warning",
                )
            return redirect(url_for("documents.detail", doc_id=doc.id))

        flash(f"{len(docs)} documento(s) enviados e indexados.", "success")
        if without_text:
            flash(
                f"{len(without_text)} arquivo(s) sem texto legível: "
                + ", ".join(d.title for d in without_text),
                "warning",
            )
        return redirect(url_for("documents.index"))

    status = 422 if request.method == "POST" else 200
    return render_template("upload.html", **_upload_context(form)), status


@bp.route("/document/<int:doc_id>")
@login_required
def detail(doc_id: int):
    doc = db.get_or_404(Document, doc_id)
    form = EditForm(obj=doc)

    kind = preview_mod.preview_kind(_ext_of(doc.original_filename))
    view = {"kind": kind, "html": None, "text": None, "rows": None, "truncated": False}
    if kind == preview_mod.MARKDOWN:
        view["html"] = preview_mod.render_markdown(doc.content)
    elif kind == preview_mod.CSV:
        view["rows"], view["truncated"] = preview_mod.render_csv(doc.content)
    elif kind == preview_mod.TEXT:
        view["text"] = doc.content

    # Planilha estruturada no banco: mostra como pseudoplanilha (aba, linhas reais)
    sheet_view = None
    if doc.sheets:
        view["kind"] = "sheet"
        wanted = request.args.get("sheet", type=int)
        current = next((s for s in doc.sheets if s.id == wanted), doc.sheets[0])
        filter_q = request.args.get("f", "", type=str).strip()[:200]
        target = request.args.get("row", 0, type=int)
        sheet_view = {
            "current": current,
            "filter": filter_q,
            "target": target,
            **sheet_page(
                current,
                page=request.args.get("page", 1, type=int),
                filter_q=filter_q,
                target_row=target,
            ),
        }
    # PDF: renderizado via <iframe> apontando para a rota /raw
    # TEXT_ONLY (office): mostra o texto extraido como previa

    return render_template(
        "document_detail.html",
        doc=doc,
        form=form,
        delete_form=DeleteForm(),
        view=view,
        sheet_view=sheet_view,
        text_preview=doc.content[:4000],
    )


@bp.route("/document/<int:doc_id>/edit", methods=["POST"])
@login_required
def edit(doc_id: int):
    doc = db.get_or_404(Document, doc_id)
    form = EditForm()
    if form.validate_on_submit():
        doc.title = form.title.data.strip()
        doc.description = (form.description.data or "").strip()
        doc.tags = (form.tags.data or "").strip()
        db.session.commit()
        flash("Alteracoes salvas.", "success")
    else:
        flash("Nao foi possivel salvar. Verifique os campos.", "danger")
    return redirect(url_for("documents.detail", doc_id=doc.id))


@bp.route("/document/<int:doc_id>/download")
@login_required
def download(doc_id: int):
    doc = db.get_or_404(Document, doc_id)
    return send_from_directory(
        current_app.config["UPLOAD_DIR"],
        doc.stored_filename,
        as_attachment=True,
        download_name=doc.original_filename,
    )


@bp.route("/document/<int:doc_id>/raw")
@login_required
def raw(doc_id: int):
    """Serve o arquivo original inline (para exibir no navegador, sem baixar)."""
    doc = db.get_or_404(Document, doc_id)
    return send_from_directory(
        current_app.config["UPLOAD_DIR"],
        doc.stored_filename,
        as_attachment=False,
        download_name=doc.original_filename,
        mimetype=doc.mime_type or None,
    )


def _get_doc_image(doc_id: int, image_id: int) -> DocumentImage:
    image = db.get_or_404(DocumentImage, image_id)
    if image.document_id != doc_id:
        abort(404)
    return image


@bp.route("/document/<int:doc_id>/image/<int:image_id>")
@login_required
def image(doc_id: int, image_id: int):
    img = _get_doc_image(doc_id, image_id)
    return send_from_directory(
        current_app.config["IMAGE_DIR"],
        img.stored_filename,
        mimetype=img.content_type or None,
    )


@bp.route("/document/<int:doc_id>/image/<int:image_id>/thumb")
@login_required
def image_thumb(doc_id: int, image_id: int):
    img = _get_doc_image(doc_id, image_id)
    return send_from_directory(current_app.config["IMAGE_DIR"], img.thumb_filename)


@bp.route("/document/<int:doc_id>/delete", methods=["POST"])
@login_required
def delete(doc_id: int):
    doc = db.get_or_404(Document, doc_id)
    if not DeleteForm().validate_on_submit():
        flash("Requisicao invalida.", "danger")
        return redirect(url_for("documents.detail", doc_id=doc.id))
    title = doc.title
    delete_document(doc)
    flash(f"Documento “{title}” removido.", "info")
    return redirect(url_for("documents.index"))
