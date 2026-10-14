import json
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .db import db


class User(UserMixin, db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    documents = db.relationship("Document", back_populates="uploader", lazy="dynamic")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return f"<User {self.username}>"


class Document(db.Model):
    __tablename__ = "document"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, default="", nullable=False)
    tags = db.Column(db.String(500), default="", nullable=False)

    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False, unique=True)
    mime_type = db.Column(db.String(120), default="", nullable=False)
    file_size = db.Column(db.Integer, default=0, nullable=False)

    # Texto extraido do arquivo (fonte da busca full-text)
    content = db.Column(db.Text, default="", nullable=False)
    extraction_ok = db.Column(db.Boolean, default=True, nullable=False)

    uploaded_by = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    uploader = db.relationship("User", back_populates="documents")
    images = db.relationship(
        "DocumentImage",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentImage.ordinal",
        lazy="selectin",
    )
    # Impressao digital para detectar duplicados (apagada pelo banco junto)
    fingerprint = db.relationship(
        "DocumentFingerprint",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    # Planilhas: abas estruturadas (linhas ficam em SheetRow, apagadas pelo banco)
    sheets = db.relationship(
        "DocumentSheet",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DocumentSheet.ordinal",
    )

    @property
    def tag_list(self):
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    @property
    def size_human(self) -> str:
        size = float(self.file_size)
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024 or unit == "GB":
                return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} GB"

    def __repr__(self) -> str:
        return f"<Document {self.id} {self.title!r}>"


class DocumentImage(db.Model):
    """Imagem extraida de dentro de um documento (PDF/DOCX/PPTX/XLSX)."""

    __tablename__ = "document_image"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(
        db.Integer,
        db.ForeignKey("document.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stored_filename = db.Column(db.String(255), nullable=False, unique=True)
    thumb_filename = db.Column(db.String(255), nullable=False)
    content_type = db.Column(db.String(60), default="", nullable=False)
    width = db.Column(db.Integer, default=0, nullable=False)
    height = db.Column(db.Integer, default=0, nullable=False)
    ordinal = db.Column(db.Integer, default=0, nullable=False)
    source_ref = db.Column(db.String(120), default="", nullable=False)

    document = db.relationship("Document", back_populates="images")

    def __repr__(self) -> str:
        return f"<DocumentImage {self.id} doc={self.document_id}>"


class DocumentSheet(db.Model):
    """Uma aba de planilha (XLSX/XLSM/XLS/CSV) com o cabecalho detectado."""

    __tablename__ = "document_sheet"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(
        db.Integer,
        db.ForeignKey("document.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ordinal = db.Column(db.Integer, default=0, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    header = db.Column(db.Text, default="[]", nullable=False)  # JSON: lista de nomes
    header_row = db.Column(db.Integer, default=0, nullable=False)  # 0 = sem cabecalho
    col_offset = db.Column(db.Integer, default=0, nullable=False)  # 1a coluna usada (0 = A)
    n_cols = db.Column(db.Integer, default=0, nullable=False)
    n_rows = db.Column(db.Integer, default=0, nullable=False)
    truncated = db.Column(db.Boolean, default=False, nullable=False)

    document = db.relationship("Document", back_populates="sheets")

    @property
    def header_list(self) -> list[str]:
        return json.loads(self.header or "[]")

    @property
    def column_letters(self) -> list[str]:
        from .sheets import column_letter

        return [column_letter(self.col_offset + i) for i in range(self.n_cols)]

    def __repr__(self) -> str:
        return f"<DocumentSheet {self.id} doc={self.document_id} {self.name!r}>"


class SheetRow(db.Model):
    """Linha de uma aba. `row_number` e o numero da linha no arquivo original."""

    __tablename__ = "sheet_row"
    __table_args__ = (db.Index("ix_sheet_row_sheet_number", "sheet_id", "row_number"),)

    id = db.Column(db.Integer, primary_key=True)
    sheet_id = db.Column(
        db.Integer,
        db.ForeignKey("document_sheet.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id = db.Column(
        db.Integer,
        db.ForeignKey("document.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    row_number = db.Column(db.Integer, nullable=False)
    cells = db.Column(db.Text, default="[]", nullable=False)  # JSON: lista de textos
    text = db.Column(db.Text, default="", nullable=False)  # celulas unidas, para busca

    @property
    def cell_list(self) -> list[str]:
        return json.loads(self.cells or "[]")


class DocumentFingerprint(db.Model):
    """Impressoes digitais de um documento, para detectar envios duplicados.

    `file_sha256`: bytes do arquivo (copia identica).
    `text_sha256`: texto extraido normalizado (mesmo conteudo salvo/exportado de
    novo). Vazio quando o texto e curto demais para comparar com seguranca.
    """

    __tablename__ = "document_fingerprint"

    document_id = db.Column(
        db.Integer,
        db.ForeignKey("document.id", ondelete="CASCADE"),
        primary_key=True,
    )
    file_sha256 = db.Column(db.String(64), nullable=False, index=True)
    text_sha256 = db.Column(db.String(64), default="", nullable=False, index=True)


class Note(db.Model):
    """Bloco de notas do usuario (painel lateral da moldura de abas).

    `clips`: JSON com os recortes trazidos das abas, cada um com a fonte:
    [{"text", "title", "url", "at"}]. `body`: texto livre para cruzar os dados.
    """

    __tablename__ = "note"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title = db.Column(db.String(120), nullable=False, default="Minhas anotações")
    body = db.Column(db.Text, nullable=False, default="")
    clips = db.Column(db.Text, nullable=False, default="[]")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @property
    def clip_list(self) -> list[dict]:
        return json.loads(self.clips or "[]")
