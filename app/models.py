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
