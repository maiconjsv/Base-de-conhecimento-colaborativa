"""Banco do Acompanhamento de Chamados (SQLite, sem dependencias).

Fica em `dados\\chamados.sqlite`, na mesma pasta de dados da Base de
Conhecimento (o backup do atualizador ja cobre). Datas sao gravadas em ISO
local ("2026-10-14T15:30:00").
"""

import json
import os
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

STATUSES = ["Aberto", "Em andamento", "Aguardando cliente", "Aguardando fornecedor",
            "Resolvido", "Fechado"]
PRIORITIES = ["P1", "P2", "P3", "P4"]
PRIORITY_NAMES = {"P1": "P1 · Crítica", "P2": "P2 · Alta", "P3": "P3 · Média", "P4": "P4 · Baixa"}

DEFAULT_SETTINGS = {
    # minutos sem atualizacao ate cobrar, por prioridade
    "cadencia": {"P1": 30, "P2": 60, "P3": 240, "P4": 480},
    # avisos antes do prazo (minutos) e repeticao depois de estourado
    "prazo_avisos": [60, 15],
    "atraso_repetir_min": 15,
    # status que nao geram alerta
    "status_pausados": ["Resolvido", "Fechado"],
    # horario de trabalho: fora dele, os alertas esperam
    "horario_inicio": "08:00",
    "horario_fim": "18:00",
    "dias_uteis": [0, 1, 2, 3, 4],          # 0 = segunda
    "p1_fora_do_horario": True,             # P1 cobra mesmo fora do horario
    "adiar_padrao_min": 15,                 # fechar o alerta no X = adiar
    "som": True,
    "sempre_visivel": False,
}


def cadence_text(minutes: int | None) -> str:
    """Texto do historico para a cadencia escolhida."""
    if minutes is None:
        return "padrão da prioridade"
    if minutes == 0:
        return "desligado (só avisos de prazo)"
    if minutes % 1440 == 0:
        n = minutes // 1440
        return f"a cada {n} dia{'s' if n > 1 else ''}"
    if minutes % 60 == 0:
        return f"a cada {minutes // 60} h"
    return f"a cada {minutes} min"


def _now() -> datetime:
    return datetime.now().replace(microsecond=0)


def to_iso(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="seconds") if dt else None


def from_iso(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def data_dir() -> Path:
    """Mesma pasta de dados da Base de Conhecimento."""
    env = os.environ.get("KB_DATA_DIR")
    if env:
        return Path(env)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "dados"
    return Path(__file__).resolve().parent.parent / "instance"


@dataclass
class Ticket:
    id: int | None = None
    numero: str = ""
    titulo: str = ""
    cliente: str = ""
    status: str = "Aberto"
    prioridade: str = "P3"
    link: str = ""
    notas: str = ""
    cadencia_min: int | None = None        # None = padrao da prioridade
    prazo: datetime | None = None
    criado_em: datetime = field(default_factory=_now)
    atualizado_em: datetime = field(default_factory=_now)
    ultimo_toque: datetime = field(default_factory=_now)   # ultimo acompanhamento
    adiado_ate: datetime | None = None
    prazo_avisos_feitos: list[int] = field(default_factory=list)
    ultimo_aviso_atraso: datetime | None = None


_SCHEMA = """
CREATE TABLE IF NOT EXISTS chamado (
    id INTEGER PRIMARY KEY,
    numero TEXT NOT NULL,
    titulo TEXT NOT NULL DEFAULT '',
    cliente TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Aberto',
    prioridade TEXT NOT NULL DEFAULT 'P3',
    link TEXT NOT NULL DEFAULT '',
    notas TEXT NOT NULL DEFAULT '',
    cadencia_min INTEGER,
    prazo TEXT,
    criado_em TEXT NOT NULL,
    atualizado_em TEXT NOT NULL,
    ultimo_toque TEXT NOT NULL,
    adiado_ate TEXT,
    prazo_avisos_feitos TEXT NOT NULL DEFAULT '[]',
    ultimo_aviso_atraso TEXT
);
CREATE INDEX IF NOT EXISTS ix_chamado_numero ON chamado(numero);
CREATE TABLE IF NOT EXISTS historico (
    id INTEGER PRIMARY KEY,
    chamado_id INTEGER NOT NULL REFERENCES chamado(id) ON DELETE CASCADE,
    em TEXT NOT NULL,
    tipo TEXT NOT NULL,
    texto TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_historico_chamado ON historico(chamado_id);
CREATE TABLE IF NOT EXISTS config (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);
"""

_COLUMNS = ["numero", "titulo", "cliente", "status", "prioridade", "link", "notas",
            "cadencia_min", "prazo", "criado_em", "atualizado_em", "ultimo_toque",
            "adiado_ate", "prazo_avisos_feitos", "ultimo_aviso_atraso"]


class Store:
    def __init__(self, path: Path | None = None):
        self.path = path or (data_dir() / "chamados.sqlite")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path))
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript(_SCHEMA)
        self.db.commit()

    # ----------------------------------------------------------- configuracao
    def settings(self) -> dict:
        out = json.loads(json.dumps(DEFAULT_SETTINGS))
        for row in self.db.execute("SELECT chave, valor FROM config"):
            try:
                out[row["chave"]] = json.loads(row["valor"])
            except ValueError:
                pass
        return out

    def save_settings(self, values: dict) -> None:
        with self.db:
            for k, v in values.items():
                self.db.execute(
                    "INSERT INTO config(chave, valor) VALUES(?, ?) "
                    "ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
                    (k, json.dumps(v, ensure_ascii=False)),
                )

    # ----------------------------------------------------------- chamados
    @staticmethod
    def _to_ticket(row) -> Ticket:
        return Ticket(
            id=row["id"], numero=row["numero"], titulo=row["titulo"], cliente=row["cliente"],
            status=row["status"], prioridade=row["prioridade"], link=row["link"],
            notas=row["notas"], cadencia_min=row["cadencia_min"], prazo=from_iso(row["prazo"]),
            criado_em=from_iso(row["criado_em"]), atualizado_em=from_iso(row["atualizado_em"]),
            ultimo_toque=from_iso(row["ultimo_toque"]), adiado_ate=from_iso(row["adiado_ate"]),
            prazo_avisos_feitos=json.loads(row["prazo_avisos_feitos"] or "[]"),
            ultimo_aviso_atraso=from_iso(row["ultimo_aviso_atraso"]),
        )

    def _values(self, t: Ticket) -> list:
        return [t.numero.strip(), t.titulo.strip(), t.cliente.strip(), t.status, t.prioridade,
                t.link.strip(), t.notas, t.cadencia_min, to_iso(t.prazo), to_iso(t.criado_em),
                to_iso(t.atualizado_em), to_iso(t.ultimo_toque), to_iso(t.adiado_ate),
                json.dumps(t.prazo_avisos_feitos), to_iso(t.ultimo_aviso_atraso)]

    def all(self, *, include_closed: bool = True) -> list[Ticket]:
        rows = self.db.execute("SELECT * FROM chamado ORDER BY id").fetchall()
        tickets = [self._to_ticket(r) for r in rows]
        if not include_closed:
            tickets = [t for t in tickets if t.status != "Fechado"]
        return tickets

    def get(self, ticket_id: int) -> Ticket | None:
        row = self.db.execute("SELECT * FROM chamado WHERE id = ?", (ticket_id,)).fetchone()
        return self._to_ticket(row) if row else None

    def find_number(self, numero: str, *, exclude_id: int | None = None) -> Ticket | None:
        row = self.db.execute(
            "SELECT * FROM chamado WHERE lower(numero) = lower(?) AND id IS NOT ?",
            (numero.strip(), exclude_id),
        ).fetchone()
        return self._to_ticket(row) if row else None

    def save(self, t: Ticket, *, history: str | None = None, history_kind: str = "nota") -> Ticket:
        """Cria ou atualiza. Registra no historico o que mudou de importante."""
        t.atualizado_em = _now()
        with self.db:
            if t.id is None:
                cur = self.db.execute(
                    f"INSERT INTO chamado({', '.join(_COLUMNS)}) VALUES({', '.join('?' * len(_COLUMNS))})",
                    self._values(t),
                )
                t.id = cur.lastrowid
                self._log(t.id, "criado", history or f"Chamado criado ({t.status}, {t.prioridade}).")
            else:
                old = self.get(t.id)
                if old and old.prazo != t.prazo:
                    # prazo novo: os avisos de prazo voltam a valer
                    t.prazo_avisos_feitos, t.ultimo_aviso_atraso = [], None
                self.db.execute(
                    f"UPDATE chamado SET {', '.join(c + ' = ?' for c in _COLUMNS)} WHERE id = ?",
                    self._values(t) + [t.id],
                )
                if old and old.status != t.status:
                    self._log(t.id, "status", f"Status: {old.status} → {t.status}")
                if old and old.prioridade != t.prioridade:
                    self._log(t.id, "prioridade", f"Prioridade: {old.prioridade} → {t.prioridade}")
                if old and old.cadencia_min != t.cadencia_min:
                    self._log(t.id, "notificacao", "Notificar cobrança: " + cadence_text(t.cadencia_min))
                if old and old.prazo != t.prazo:
                    novo = t.prazo.strftime("%d/%m/%Y %H:%M") if t.prazo else "sem prazo"
                    self._log(t.id, "prazo", f"Prazo: {novo}")
                if history:
                    self._log(t.id, history_kind, history)
        return t

    def delete(self, ticket_id: int) -> None:
        with self.db:
            self.db.execute("DELETE FROM chamado WHERE id = ?", (ticket_id,))

    # ----------------------------------------------------------- historico
    def _log(self, ticket_id: int, tipo: str, texto: str) -> None:
        self.db.execute(
            "INSERT INTO historico(chamado_id, em, tipo, texto) VALUES(?, ?, ?, ?)",
            (ticket_id, to_iso(_now()), tipo, texto),
        )

    def history(self, ticket_id: int) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT em, tipo, texto FROM historico WHERE chamado_id = ? ORDER BY id DESC", (ticket_id,)
        ).fetchall()

    # ----------------------------------------------------------- acoes rapidas
    def touch(self, ticket_id: int, nota: str = "") -> None:
        """Registrar acompanhamento: zera a cadencia (e o adiamento)."""
        t = self.get(ticket_id)
        if not t:
            return
        t.ultimo_toque = _now()
        t.adiado_ate = None
        self.save(t, history_kind="acompanhamento",
                  history=("Acompanhamento: " + nota.strip()) if nota.strip() else "Acompanhamento registrado.")

    def snooze(self, ticket_id: int, until: datetime) -> None:
        t = self.get(ticket_id)
        if not t:
            return
        t.adiado_ate = until
        with self.db:
            self.db.execute("UPDATE chamado SET adiado_ate = ? WHERE id = ?", (to_iso(until), ticket_id))
            self._log(ticket_id, "adiado", f"Alerta adiado até {until.strftime('%d/%m %H:%M')}.")

    def mark_deadline_alert(self, ticket_id: int, *, pre: int | None = None, overdue: bool = False) -> None:
        t = self.get(ticket_id)
        if not t:
            return
        if pre is not None and pre not in t.prazo_avisos_feitos:
            t.prazo_avisos_feitos.append(pre)
        if overdue:
            t.ultimo_aviso_atraso = _now()
        with self.db:
            self.db.execute(
                "UPDATE chamado SET prazo_avisos_feitos = ?, ultimo_aviso_atraso = ? WHERE id = ?",
                (json.dumps(t.prazo_avisos_feitos), to_iso(t.ultimo_aviso_atraso), ticket_id),
            )
