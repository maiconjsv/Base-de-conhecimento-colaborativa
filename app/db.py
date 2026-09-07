"""Objeto SQLAlchemy e criacao do indice de busca (SQLite FTS5).

A tabela virtual `document_fts` usa a tabela `document` como conteudo externo
(`content='document'`). Triggers mantem o indice sincronizado automaticamente a
cada INSERT/UPDATE/DELETE em `document`.
"""

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event, text

db = SQLAlchemy()


_FTS_SCHEMA = [
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS document_fts USING fts5(
        title,
        description,
        tags,
        content,
        content='document',
        content_rowid='id',
        tokenize="unicode61 remove_diacritics 2"
    );
    """,
    """
    CREATE TRIGGER IF NOT EXISTS document_ai AFTER INSERT ON document BEGIN
        INSERT INTO document_fts(rowid, title, description, tags, content)
        VALUES (new.id, new.title, new.description, new.tags, new.content);
    END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS document_ad AFTER DELETE ON document BEGIN
        INSERT INTO document_fts(document_fts, rowid, title, description, tags, content)
        VALUES ('delete', old.id, old.title, old.description, old.tags, old.content);
    END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS document_au AFTER UPDATE ON document BEGIN
        INSERT INTO document_fts(document_fts, rowid, title, description, tags, content)
        VALUES ('delete', old.id, old.title, old.description, old.tags, old.content);
        INSERT INTO document_fts(rowid, title, description, tags, content)
        VALUES (new.id, new.title, new.description, new.tags, new.content);
    END;
    """,
]


def _enable_sqlite_fk(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def init_engine_pragmas(engine):
    """Liga foreign keys em toda conexao SQLite."""
    if engine.url.get_backend_name() == "sqlite":
        event.listen(engine, "connect", _enable_sqlite_fk)


def create_fts(session):
    """Cria a tabela FTS5 e os triggers (idempotente)."""
    for stmt in _FTS_SCHEMA:
        session.execute(text(stmt))
    session.commit()


def rebuild_fts(session):
    """Reconstroi o indice a partir do conteudo atual da tabela `document`."""
    session.execute(
        text("INSERT INTO document_fts(document_fts) VALUES ('rebuild')")
    )
    session.commit()
