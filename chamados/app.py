"""Interface do Acompanhamento de Chamados (tkinter: janela nativa, sem navegador).

Janela principal: lista compacta (numero, titulo, status, prioridade, proxima
cobranca, prazo), detalhes com historico e anotacao rapida. A cada TICK_MS as
regras de `alertas.py` rodam; o que vencer aparece na janela de cobranca, que
fica por cima de tudo, toca um som e pisca na barra de tarefas.
"""

import csv
import ctypes
import os
import subprocess
import sys
import tkinter as tk
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import alertas
from .store import PRIORITIES, PRIORITY_NAMES, STATUSES, Store, Ticket

APP_TITLE = "Acompanhamento de Chamados"
TICK_MS = 20_000

# Paleta Semantix (mesma do sistema web)
C = {
    "brand": "#5A179A", "brand_dark": "#2E0A5E", "brand_050": "#F6F1FB", "brand_100": "#EDE3F7",
    "ink": "#241B31", "muted": "#6B6478", "line": "#E7E1F0", "surface": "#FFFFFF", "bg": "#F7F5FA",
    "late_bg": "#FDE2E1", "late_fg": "#9B1C1C", "warn_bg": "#FFF1D6", "warn_fg": "#7A4E00",
    "soon_bg": "#FFF9E6", "paused_fg": "#9A93A6",
}
FONT = ("Segoe UI", 10)
FONT_B = ("Segoe UI", 10, "bold")


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
def parse_when(text: str) -> datetime | None:
    """'14/10/2026 18:00', '14/10 18:00', '18:00' (hoje) ou '' (sem prazo)."""
    text = (text or "").strip()
    if not text:
        return None
    now = datetime.now()
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%y %H:%M", "%d/%m %H:%M", "%H:%M", "%d/%m/%Y"):
        try:
            dt = datetime.strptime(text, fmt)
        except ValueError:
            continue
        if fmt == "%H:%M":
            dt = now.replace(hour=dt.hour, minute=dt.minute, second=0, microsecond=0)
        elif fmt == "%d/%m %H:%M":
            dt = dt.replace(year=now.year)
        elif fmt == "%d/%m/%Y":
            dt = dt.replace(hour=18)
        return dt
    raise ValueError(text)


UNITS = {"minuto(s)": 1, "hora(s)": 60, "dia(s)": 1440}
NOTIFY_PRESETS = [("15 min", 15), ("30 min", 30), ("1 h", 60), ("2 h", 120), ("4 h", 240), ("1 dia", 1440)]


def split_minutes(minutes: int) -> tuple[int, str]:
    """90 -> (90, 'minuto(s)'); 120 -> (2, 'hora(s)'); 2880 -> (2, 'dia(s)')."""
    if minutes and minutes % 1440 == 0:
        return minutes // 1440, "dia(s)"
    if minutes and minutes % 60 == 0:
        return minutes // 60, "hora(s)"
    return minutes, "minuto(s)"


def when_text(dt: datetime) -> str:
    now = datetime.now()
    if dt.date() == now.date():
        return f"hoje às {dt:%H:%M}"
    if dt.date() == (now + timedelta(days=1)).date():
        return f"amanhã às {dt:%H:%M}"
    return f"{dt:%d/%m} às {dt:%H:%M}"


def fmt_when(dt: datetime | None) -> str:
    return dt.strftime("%d/%m/%Y %H:%M") if dt else ""


def beep() -> None:
    try:
        import winsound
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
    except Exception:  # noqa: BLE001
        pass


def flash(window) -> None:
    """Pisca o botao da janela na barra de tarefas (Windows)."""
    if os.name != "nt":
        return

    class FLASHWINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("hwnd", ctypes.c_void_p), ("dwFlags", ctypes.c_uint),
                    ("uCount", ctypes.c_uint), ("dwTimeout", ctypes.c_uint)]

    try:
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        info = FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd, 0x3 | 0xC, 0, 0)  # ALL | TIMERNOFG
        ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))
    except Exception:  # noqa: BLE001
        pass


def startup_shortcut() -> Path:
    return (Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
            / "Startup" / f"{APP_TITLE}.lnk")


def set_startup(enabled: bool) -> str:
    """Cria/remove o atalho na pasta Inicializar do Windows. Devolve erro ou ''."""
    link = startup_shortcut()
    if not enabled:
        link.unlink(missing_ok=True)
        return ""
    if not getattr(sys, "frozen", False):
        return "Disponível só no programa instalado (.exe)."
    exe = sys.executable.replace("'", "''")
    cmd = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{str(link).replace(chr(39), chr(39) * 2)}');"
           f"$s.TargetPath='{exe}';$s.WorkingDirectory='{str(Path(sys.executable).parent).replace(chr(39), chr(39) * 2)}';"
           "$s.Save()")
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
                       capture_output=True, text=True, creationflags=0x08000000)
    return "" if r.returncode == 0 else (r.stderr.strip() or "falha ao criar o atalho")


def asset(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    for p in (base / "app" / "static" / name, base / name):
        if p.exists():
            return p
    return base / name


# --------------------------------------------------------------------------- #
# Dialogo de chamado (novo / editar)
# --------------------------------------------------------------------------- #
class TicketDialog(tk.Toplevel):
    def __init__(self, master, store: Store, ticket: Ticket | None = None):
        super().__init__(master)
        self.store, self.result = store, None
        self.ticket = ticket or Ticket(status="Aberto", prioridade="P3")
        self.settings = store.settings()
        self.title("Editar chamado" if ticket else "Novo chamado")
        self.configure(bg=C["bg"], padx=16, pady=14)
        self.transient(master)
        self.resizable(False, False)

        t = self.ticket
        self.v = {
            "numero": tk.StringVar(value=t.numero), "titulo": tk.StringVar(value=t.titulo),
            "cliente": tk.StringVar(value=t.cliente), "status": tk.StringVar(value=t.status),
            "prioridade": tk.StringVar(value=PRIORITY_NAMES[t.prioridade]), "link": tk.StringVar(value=t.link),
            "prazo": tk.StringVar(value=fmt_when(t.prazo)),
        }
        mode = "padrao" if t.cadencia_min is None else ("off" if t.cadencia_min == 0 else "custom")
        n, unit = split_minutes(t.cadencia_min or self.settings["cadencia"].get(t.prioridade, 240))
        self.v.update({
            "notify_mode": tk.StringVar(value=mode),
            "notify_n": tk.StringVar(value=str(n)),
            "notify_unit": tk.StringVar(value=unit),
        })
        row = 0

        def label(text, r):
            ttk.Label(self, text=text, style="Field.TLabel").grid(row=r, column=0, sticky="w", pady=4, padx=(0, 10))

        label("Número *", row)
        e_num = ttk.Entry(self, textvariable=self.v["numero"], width=22)
        e_num.grid(row=row, column=1, sticky="w")
        row += 1
        label("Título", row)
        ttk.Entry(self, textvariable=self.v["titulo"], width=52).grid(row=row, column=1, columnspan=3, sticky="we")
        row += 1
        label("Cliente / sistema", row)
        ttk.Entry(self, textvariable=self.v["cliente"], width=30).grid(row=row, column=1, sticky="w")
        row += 1
        label("Status", row)
        ttk.Combobox(self, textvariable=self.v["status"], values=STATUSES, state="readonly", width=22
                     ).grid(row=row, column=1, sticky="w")
        row += 1
        label("Prioridade", row)
        cb = ttk.Combobox(self, textvariable=self.v["prioridade"], values=[PRIORITY_NAMES[p] for p in PRIORITIES],
                          state="readonly", width=22)
        cb.grid(row=row, column=1, sticky="w")
        cb.bind("<<ComboboxSelected>>", lambda e: self._sync_notify())
        row += 1
        label("Link do chamado", row)
        ttk.Entry(self, textvariable=self.v["link"], width=52).grid(row=row, column=1, columnspan=3, sticky="we")
        row += 1

        label("Prazo", row)
        box = ttk.Frame(self, style="Bg.TFrame")
        box.grid(row=row, column=1, columnspan=3, sticky="w")
        ttk.Entry(box, textvariable=self.v["prazo"], width=18).pack(side="left")
        for txt, fn in (("+1 h", lambda: timedelta(hours=1)), ("+4 h", lambda: timedelta(hours=4)),
                        ("Hoje 18h", None), ("Amanhã 18h", "amanha"), ("Sem prazo", "")):
            ttk.Button(box, text=txt, style="Small.TButton",
                       command=lambda f=fn: self._quick_deadline(f)).pack(side="left", padx=(6, 0))
        row += 1
        ttk.Label(self, text="dd/mm/aaaa hh:mm · ou só hh:mm para hoje", style="Hint.TLabel"
                  ).grid(row=row, column=1, columnspan=3, sticky="w")
        row += 1

        box = ttk.LabelFrame(self, text="  🔔  Notificar cobrança  ", style="Notify.TLabelframe", padding=(12, 8))
        box.grid(row=row, column=0, columnspan=4, sticky="we", pady=(10, 6))
        line = ttk.Frame(box, style="Card.TFrame")
        line.pack(fill="x")
        ttk.Radiobutton(line, text="A cada", value="custom", variable=self.v["notify_mode"],
                        command=self._sync_notify, style="Card.TRadiobutton").pack(side="left")
        self.n_spin = ttk.Spinbox(line, from_=1, to=999, textvariable=self.v["notify_n"], width=5,
                                  command=self._sync_notify)
        self.n_spin.pack(side="left", padx=(6, 4))
        self.unit_cb = ttk.Combobox(line, textvariable=self.v["notify_unit"], values=list(UNITS),
                                    state="readonly", width=8)
        self.unit_cb.pack(side="left")
        self.unit_cb.bind("<<ComboboxSelected>>", lambda e: self._sync_notify())
        presets = ttk.Frame(box, style="Card.TFrame")
        presets.pack(fill="x", pady=(6, 2), padx=(22, 0))
        for text, minutes in NOTIFY_PRESETS:
            ttk.Button(presets, text=text, style="Small.TButton",
                       command=lambda m=minutes: self._preset(m)).pack(side="left", padx=(0, 4))
        self.default_rb = ttk.Radiobutton(box, value="padrao", variable=self.v["notify_mode"],
                                          command=self._sync_notify, style="Card.TRadiobutton")
        self.default_rb.pack(anchor="w", pady=(4, 0))
        ttk.Radiobutton(box, text="Não notificar (só os avisos de prazo)", value="off",
                        variable=self.v["notify_mode"], command=self._sync_notify,
                        style="Card.TRadiobutton").pack(anchor="w")
        self.notify_preview = ttk.Label(box, text="", style="Preview.TLabel", wraplength=470, justify="left")
        self.notify_preview.pack(anchor="w", pady=(6, 0))
        self.v["notify_n"].trace_add("write", lambda *a: self._sync_notify())
        row += 1

        label("Notas", row)
        self.notes = tk.Text(self, width=52, height=5, font=FONT, relief="solid", bd=1, wrap="word")
        self.notes.insert("1.0", t.notas)
        self.notes.grid(row=row, column=1, columnspan=3, sticky="we", pady=4)
        row += 1

        btns = ttk.Frame(self, style="Bg.TFrame")
        btns.grid(row=row, column=0, columnspan=4, sticky="e", pady=(10, 0))
        ttk.Button(btns, text="Cancelar", command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(btns, text="Salvar", style="Accent.TButton", command=self._save).pack(side="right")

        self._sync_notify()
        self.bind("<Return>", lambda e: self._save() if e.widget is not self.notes else None)
        self.bind("<Escape>", lambda e: self.destroy())
        e_num.focus_set()
        self.grab_set()
        self.update_idletasks()
        self.geometry(f"+{master.winfo_rootx() + 60}+{master.winfo_rooty() + 40}")

    def _prio(self) -> str:
        return self.v["prioridade"].get().split(" ")[0]

    def _notify_minutes(self) -> int | None:
        """None = padrao da prioridade; 0 = desligado; senao minutos. ValueError se invalido."""
        mode = self.v["notify_mode"].get()
        if mode == "padrao":
            return None
        if mode == "off":
            return 0
        n = int(self.v["notify_n"].get())
        if n < 1:
            raise ValueError
        return n * UNITS[self.v["notify_unit"].get()]

    def _preset(self, minutes: int):
        n, unit = split_minutes(minutes)
        self.v["notify_mode"].set("custom")
        self.v["notify_unit"].set(unit)
        self.v["notify_n"].set(str(n))
        self._sync_notify()

    def _sync_notify(self):
        default = self.settings["cadencia"].get(self._prio(), 240)
        self.default_rb.config(text=f"Padrão da prioridade {self._prio()} (a cada {alertas.fmt_duration(default)})")
        custom = self.v["notify_mode"].get() == "custom"
        for w in (self.n_spin,):
            w.state(["!disabled"] if custom else ["disabled"])
        self.unit_cb.state(["!disabled", "readonly"] if custom else ["disabled"])
        try:
            minutes = self._notify_minutes()
        except (ValueError, KeyError):
            self.notify_preview.config(text="Informe um número inteiro.")
            return
        if minutes is None:
            minutes = default
        if minutes == 0:
            self.notify_preview.config(text="Sem lembretes periódicos: você só será avisado do prazo, se houver.")
            return
        base = self.ticket.ultimo_toque if self.ticket.id else datetime.now()
        nxt = max(base + timedelta(minutes=minutes), datetime.now())
        self.notify_preview.config(
            text=f"Você será avisado a cada {alertas.fmt_duration(minutes)} sem acompanhamento. "
                 f"Próximo aviso: {when_text(nxt)}.")

    def _quick_deadline(self, how):
        now = datetime.now().replace(second=0, microsecond=0)
        if how == "":
            self.v["prazo"].set("")
            return
        if how is None:
            dt = now.replace(hour=18, minute=0)
        elif how == "amanha":
            dt = (now + timedelta(days=1)).replace(hour=18, minute=0)
        else:
            base = parse_when(self.v["prazo"].get()) if self.v["prazo"].get().strip() else now
            dt = (base or now) + how()
        self.v["prazo"].set(fmt_when(dt))

    def _save(self):
        numero = self.v["numero"].get().strip()
        if not numero:
            messagebox.showwarning(APP_TITLE, "Informe o número do chamado.", parent=self)
            return
        try:
            prazo = parse_when(self.v["prazo"].get())
        except ValueError:
            messagebox.showwarning(APP_TITLE, "Prazo inválido. Use dd/mm/aaaa hh:mm (ex.: 14/10/2026 18:00).",
                                   parent=self)
            return
        try:
            cad = self._notify_minutes()
        except (ValueError, KeyError):
            messagebox.showwarning(APP_TITLE, "Em “Notificar cobrança”, informe a cada quanto tempo "
                                              "(número inteiro).", parent=self)
            return
        other = self.store.find_number(numero, exclude_id=self.ticket.id)
        if other and not messagebox.askyesno(
                APP_TITLE, f"Já existe o chamado {other.numero} ({other.status}). Salvar mesmo assim?", parent=self):
            return
        t = self.ticket
        t.numero, t.titulo, t.cliente = numero, self.v["titulo"].get(), self.v["cliente"].get()
        t.status, t.prioridade, t.link = self.v["status"].get(), self._prio(), self.v["link"].get()
        t.prazo, t.cadencia_min, t.notas = prazo, cad, self.notes.get("1.0", "end").rstrip()
        self.result = self.store.save(t)
        self.destroy()


# --------------------------------------------------------------------------- #
# Configuracoes
# --------------------------------------------------------------------------- #
class SettingsDialog(tk.Toplevel):
    def __init__(self, master, store: Store):
        super().__init__(master)
        self.store, self.saved = store, False
        s = store.settings()
        self.title("Configurações dos alertas")
        self.configure(bg=C["bg"], padx=16, pady=14)
        self.transient(master)
        self.resizable(False, False)

        self.cad = {p: tk.StringVar(value=str(s["cadencia"].get(p, 240))) for p in PRIORITIES}
        self.avisos = tk.StringVar(value=", ".join(str(x) for x in s["prazo_avisos"]))
        self.atraso = tk.StringVar(value=str(s["atraso_repetir_min"]))
        self.inicio = tk.StringVar(value=s["horario_inicio"])
        self.fim = tk.StringVar(value=s["horario_fim"])
        self.dias = [tk.BooleanVar(value=d in s["dias_uteis"]) for d in range(7)]
        self.p1 = tk.BooleanVar(value=s["p1_fora_do_horario"])
        self.adiar = tk.StringVar(value=str(s["adiar_padrao_min"]))
        self.som = tk.BooleanVar(value=s["som"])
        self.iniciar = tk.BooleanVar(value=startup_shortcut().exists())
        self.pausados = {st: tk.BooleanVar(value=st in s["status_pausados"]) for st in STATUSES}

        r = 0
        ttk.Label(self, text="Cobrar acompanhamento a cada (minutos, por prioridade)", style="Section.TLabel"
                  ).grid(row=r, column=0, columnspan=4, sticky="w")
        r += 1
        f = ttk.Frame(self, style="Bg.TFrame")
        f.grid(row=r, column=0, columnspan=4, sticky="w", pady=(2, 10))
        for p in PRIORITIES:
            ttk.Label(f, text=PRIORITY_NAMES[p], style="Field.TLabel").pack(side="left", padx=(0, 4))
            ttk.Spinbox(f, from_=5, to=10080, increment=5, textvariable=self.cad[p], width=6).pack(side="left", padx=(0, 14))
        r += 1

        ttk.Label(self, text="Prazos", style="Section.TLabel").grid(row=r, column=0, columnspan=4, sticky="w")
        r += 1
        ttk.Label(self, text="Avisar antes do prazo (min)", style="Field.TLabel").grid(row=r, column=0, sticky="w")
        ttk.Entry(self, textvariable=self.avisos, width=14).grid(row=r, column=1, sticky="w")
        ttk.Label(self, text="ex.: 60, 15", style="Hint.TLabel").grid(row=r, column=2, sticky="w", padx=6)
        r += 1
        ttk.Label(self, text="Prazo estourado: repetir a cada (min)", style="Field.TLabel").grid(row=r, column=0, sticky="w")
        ttk.Spinbox(self, from_=1, to=1440, textvariable=self.atraso, width=6).grid(row=r, column=1, sticky="w", pady=(2, 10))
        r += 1

        ttk.Label(self, text="Horário de trabalho (fora dele os alertas esperam)", style="Section.TLabel"
                  ).grid(row=r, column=0, columnspan=4, sticky="w")
        r += 1
        f = ttk.Frame(self, style="Bg.TFrame")
        f.grid(row=r, column=0, columnspan=4, sticky="w")
        ttk.Entry(f, textvariable=self.inicio, width=6).pack(side="left")
        ttk.Label(f, text="às", style="Field.TLabel").pack(side="left", padx=4)
        ttk.Entry(f, textvariable=self.fim, width=6).pack(side="left", padx=(0, 14))
        for i, nome in enumerate(["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]):
            ttk.Checkbutton(f, text=nome, variable=self.dias[i]).pack(side="left")
        r += 1
        ttk.Checkbutton(self, text="P1 (crítica) cobra mesmo fora do horário", variable=self.p1
                        ).grid(row=r, column=0, columnspan=4, sticky="w", pady=(2, 10))
        r += 1

        ttk.Label(self, text="Status que não geram alerta", style="Section.TLabel").grid(row=r, column=0, columnspan=4, sticky="w")
        r += 1
        f = ttk.Frame(self, style="Bg.TFrame")
        f.grid(row=r, column=0, columnspan=4, sticky="w", pady=(2, 10))
        for st in STATUSES:
            ttk.Checkbutton(f, text=st, variable=self.pausados[st]).pack(side="left", padx=(0, 6))
        r += 1

        ttk.Label(self, text="Geral", style="Section.TLabel").grid(row=r, column=0, columnspan=4, sticky="w")
        r += 1
        ttk.Label(self, text="Fechar o alerta no X adia por (min)", style="Field.TLabel").grid(row=r, column=0, sticky="w")
        ttk.Spinbox(self, from_=1, to=480, textvariable=self.adiar, width=6).grid(row=r, column=1, sticky="w")
        r += 1
        ttk.Checkbutton(self, text="Tocar som nos alertas", variable=self.som).grid(row=r, column=0, columnspan=2, sticky="w")
        r += 1
        ttk.Checkbutton(self, text="Abrir junto com o Windows", variable=self.iniciar).grid(row=r, column=0, columnspan=2, sticky="w")
        r += 1

        b = ttk.Frame(self, style="Bg.TFrame")
        b.grid(row=r, column=0, columnspan=4, sticky="e", pady=(12, 0))
        ttk.Button(b, text="Cancelar", command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(b, text="Salvar", style="Accent.TButton", command=self._save).pack(side="right")
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()
        self.geometry(f"+{master.winfo_rootx() + 60}+{master.winfo_rooty() + 40}")

    def _save(self):
        try:
            cad = {p: max(1, int(v.get())) for p, v in self.cad.items()}
            avisos = sorted({int(x) for x in self.avisos.get().replace(";", ",").split(",") if x.strip()}, reverse=True)
            atraso, adiar = max(1, int(self.atraso.get())), max(1, int(self.adiar.get()))
            for hh in (self.inicio.get(), self.fim.get()):
                datetime.strptime(hh.strip(), "%H:%M")
        except ValueError:
            messagebox.showwarning(APP_TITLE, "Confira os números e os horários (formato hh:mm).", parent=self)
            return
        self.store.save_settings({
            "cadencia": cad, "prazo_avisos": avisos, "atraso_repetir_min": atraso,
            "horario_inicio": self.inicio.get().strip(), "horario_fim": self.fim.get().strip(),
            "dias_uteis": [i for i, v in enumerate(self.dias) if v.get()],
            "p1_fora_do_horario": self.p1.get(), "adiar_padrao_min": adiar, "som": self.som.get(),
            "status_pausados": [st for st, v in self.pausados.items() if v.get()],
        })
        if self.iniciar.get() != startup_shortcut().exists():
            err = set_startup(self.iniciar.get())
            if err:
                messagebox.showinfo(APP_TITLE, f"Não deu para configurar a abertura com o Windows: {err}", parent=self)
        self.saved = True
        self.destroy()


# --------------------------------------------------------------------------- #
# Janela de cobranca
# --------------------------------------------------------------------------- #
class AlertWindow(tk.Toplevel):
    """Lista os chamados a cobrar; fica por cima de tudo ate a pessoa agir."""

    def __init__(self, app: "App"):
        super().__init__(app.root)
        self.app = app
        self.title("Cobrança de chamados")
        self.configure(bg=C["surface"])
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self.snooze_all_default)
        head = tk.Frame(self, bg=C["late_fg"])
        head.pack(fill="x")
        self.head_lbl = tk.Label(head, text="", bg=C["late_fg"], fg="white", font=("Segoe UI", 11, "bold"),
                                 padx=14, pady=8, anchor="w")
        self.head_lbl.pack(side="left", fill="x", expand=True)
        self.body = tk.Frame(self, bg=C["surface"], padx=12, pady=8)
        self.body.pack(fill="both", expand=True)
        foot = tk.Frame(self, bg=C["bg"], padx=12, pady=8)
        foot.pack(fill="x")
        ttk.Button(foot, text="Adiar todos 15 min", command=lambda: self.snooze_all(15)).pack(side="right")
        ttk.Label(foot, text="Fechar no X adia pelo tempo padrão das configurações.", style="Hint.TLabel").pack(side="left")
        # chamado -> alerta mostrado. Um motivo (ex.: "prazo estourado") fica no
        # cartao ate a pessoa agir, mesmo que a regra so dispare uma vez.
        self.items: dict[int, alertas.Alert] = {}

    @property
    def shown(self) -> set[int]:
        return set(self.items)

    @staticmethod
    def _kind(reason: str) -> str:
        """Assunto do motivo: "Prazo …" (vence/estourado) ou "Sem acompanhamento"."""
        return "Prazo" if reason.startswith("Prazo") else reason.split(" há ")[0]

    def merge(self, alerts: list) -> bool:
        """Junta os alertas novos aos que ja estao na tela. True se entrou chamado novo."""
        new = False
        for a in alerts:
            old = self.items.get(a.ticket.id)
            if old is None:
                self.items[a.ticket.id] = a
                new = True
                continue
            kinds = {self._kind(r) for r in a.reasons}
            a.reasons = a.reasons + [r for r in old.reasons if self._kind(r) not in kinds]
            a.severity = max(a.severity, old.severity)
            self.items[a.ticket.id] = a
        return new

    def show(self) -> None:
        alerts = sorted(self.items.values(), key=lambda x: (-x.severity, x.ticket.prioridade, x.ticket.numero))
        signature = [(a.ticket.id, tuple(a.reasons)) for a in alerts]
        if signature == getattr(self, "_signature", None) and self.state() != "withdrawn":
            return                # nada mudou: nao redesenha (nao fecha um menu aberto)
        self._signature = signature
        for w in self.body.winfo_children():
            w.destroy()
        n = len(alerts)
        self.head_lbl.config(text=f"{n} chamado{'s' if n > 1 else ''} para acompanhar agora")
        for a in alerts:
            self._card(a)
        self.update_idletasks()
        w = max(520, self.winfo_reqwidth())
        h = min(self.winfo_reqheight(), int(self.winfo_screenheight() * 0.8))
        x = self.winfo_screenwidth() - w - 24
        y = self.winfo_screenheight() - h - 72
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.deiconify()
        self.lift()

    def _card(self, a):
        t = a.ticket
        color = {2: C["late_fg"], 1: C["warn_fg"]}.get(a.severity, C["brand"])
        card = tk.Frame(self.body, bg=C["surface"], highlightthickness=1, highlightbackground=C["line"], padx=10, pady=8)
        card.pack(fill="x", pady=4)
        tk.Frame(card, bg=color, width=4).pack(side="left", fill="y", padx=(0, 10))
        info = tk.Frame(card, bg=C["surface"])
        info.pack(side="left", fill="both", expand=True)
        tk.Label(info, text=f"{t.numero}   ·   {t.prioridade}   ·   {t.status}", bg=C["surface"], fg=C["ink"],
                 font=FONT_B, anchor="w").pack(fill="x")
        if t.titulo:
            tk.Label(info, text=t.titulo, bg=C["surface"], fg=C["muted"], font=FONT, anchor="w",
                     wraplength=420, justify="left").pack(fill="x")
        for reason in a.reasons:
            tk.Label(info, text="● " + reason, bg=C["surface"], fg=color, font=FONT, anchor="w").pack(fill="x")
        btns = tk.Frame(info, bg=C["surface"])
        btns.pack(fill="x", pady=(6, 0))
        ttk.Button(btns, text="Registrar acompanhamento", style="Accent.TButton",
                   command=lambda: self.app.touch_dialog(t.id, from_alert=self)).pack(side="left")
        every = alertas.cadence_minutes(t, self.app.store.settings()) or 15
        ttk.Button(btns, text=f"Vi, lembrar em {alertas.fmt_duration(every)}",
                   command=lambda: self.snooze(t.id, every)).pack(side="left", padx=(6, 0))
        mb = ttk.Menubutton(btns, text="Adiar")
        menu = tk.Menu(mb, tearoff=False)
        for label, minutes in (("15 min", 15), ("30 min", 30), ("1 hora", 60), ("2 horas", 120)):
            menu.add_command(label=label, command=lambda m=minutes: self.snooze(t.id, m))
        menu.add_command(label="Amanhã 9h", command=lambda: self.snooze(t.id, None))
        mb["menu"] = menu
        mb.pack(side="left", padx=6)
        ttk.Button(btns, text="Copiar nº", command=lambda: self.app.copy_number(t)).pack(side="left")
        if t.link:
            ttk.Button(btns, text="Abrir", command=lambda: webbrowser.open(t.link)).pack(side="left", padx=6)

    def snooze(self, ticket_id: int, minutes: int | None):
        now = datetime.now().replace(second=0, microsecond=0)
        until = now + timedelta(minutes=minutes) if minutes else (now + timedelta(days=1)).replace(hour=9, minute=0)
        self.app.store.snooze(ticket_id, until)
        self.done(ticket_id)

    def snooze_all(self, minutes: int):
        until = datetime.now().replace(second=0, microsecond=0) + timedelta(minutes=minutes)
        for tid in list(self.items):
            self.app.store.snooze(tid, until)
        self.items.clear()
        self._signature = None
        self.withdraw()
        self.app.refresh()

    def snooze_all_default(self):
        self.snooze_all(int(self.app.store.settings().get("adiar_padrao_min", 15)))

    def done(self, ticket_id: int):
        """A pessoa agiu sobre o chamado: tira da lista; fecha se acabou."""
        self.items.pop(ticket_id, None)
        self._signature = None
        if not self.items:
            self.withdraw()
        else:
            self.show()
        self.app.refresh()


# --------------------------------------------------------------------------- #
# Janela principal
# --------------------------------------------------------------------------- #
COLUMNS = [("numero", "Nº", 110), ("titulo", "Título", 240), ("cliente", "Cliente", 110),
           ("status", "Status", 170), ("prioridade", "Prior.", 50),
           ("notificar", "Notificar", 120), ("cobranca", "Próxima cobrança", 160), ("prazo", "Prazo", 170)]


class App:
    def __init__(self, store: Store):
        self.store = store
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry("1040x600")
        self.root.minsize(720, 420)
        self.root.configure(bg=C["bg"])
        try:
            self._icon = tk.PhotoImage(file=str(asset("favicon.png")))
            self.root.iconphoto(True, self._icon)
        except tk.TclError:
            pass
        self._style()
        self.alert_win: AlertWindow | None = None
        self.show_closed = tk.BooleanVar(value=False)
        self.topmost = tk.BooleanVar(value=bool(store.settings().get("sempre_visivel")))
        self.filter = tk.StringVar()
        self.filter.trace_add("write", lambda *a: self.refresh())
        self._build()
        self.root.attributes("-topmost", self.topmost.get())
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.refresh()
        self.root.after(1500, self._tick)

    # ----------------------------------------------------------- aparencia
    def _style(self):
        st = ttk.Style(self.root)
        st.theme_use("clam")
        self.root.option_add("*Font", FONT)
        st.configure(".", font=FONT, background=C["bg"], foreground=C["ink"])
        st.configure("Bg.TFrame", background=C["bg"])
        st.configure("Field.TLabel", background=C["bg"], foreground=C["ink"])
        st.configure("Hint.TLabel", background=C["bg"], foreground=C["muted"], font=("Segoe UI", 9))
        st.configure("Section.TLabel", background=C["bg"], foreground=C["brand"], font=FONT_B)
        st.configure("TButton", padding=(10, 4), background=C["surface"], bordercolor=C["line"])
        st.map("TButton", background=[("active", C["brand_050"])])
        st.configure("Small.TButton", padding=(6, 1))
        st.configure("Accent.TButton", background=C["brand"], foreground="white", bordercolor=C["brand"])
        st.map("Accent.TButton", background=[("active", C["brand_dark"]), ("disabled", "#B389DC")],
               foreground=[("disabled", "white")])
        st.configure("TCheckbutton", background=C["bg"])
        st.configure("Notify.TLabelframe", background=C["surface"], bordercolor=C["brand"], relief="solid")
        st.configure("Notify.TLabelframe.Label", background=C["bg"], foreground=C["brand"], font=FONT_B)
        st.configure("Card.TFrame", background=C["surface"])
        st.configure("Card.TRadiobutton", background=C["surface"])
        st.configure("Preview.TLabel", background=C["surface"], foreground=C["brand_dark"], font=FONT_B)
        st.configure("TMenubutton", padding=(10, 4), background=C["surface"])
        st.configure("Treeview", rowheight=28, background=C["surface"], fieldbackground=C["surface"],
                     bordercolor=C["line"])
        st.configure("Treeview.Heading", font=FONT_B, background=C["brand_100"], foreground=C["brand_dark"],
                     relief="flat", padding=(6, 4))
        st.map("Treeview", background=[("selected", C["brand"])], foreground=[("selected", "white")])

    def _build(self):
        head = tk.Frame(self.root, bg=C["brand"], padx=14, pady=8)
        head.pack(fill="x")
        tk.Label(head, text="Chamados", bg=C["brand"], fg="white", font=("Segoe UI", 13, "bold")).pack(side="left")
        self.summary = tk.Label(head, text="", bg=C["brand"], fg="#E7DCF5", font=FONT)
        self.summary.pack(side="left", padx=14)
        ttk.Checkbutton(head, text="Sempre visível", variable=self.topmost, command=self._toggle_top,
                        style="Head.TCheckbutton").pack(side="right")
        ent = ttk.Entry(head, textvariable=self.filter, width=24)
        ent.pack(side="right", padx=(0, 16))
        tk.Label(head, text="Filtrar", bg=C["brand"], fg="#E7DCF5", font=FONT).pack(side="right", padx=(0, 6))
        ttk.Style(self.root).configure("Head.TCheckbutton", background=C["brand"], foreground="white")
        ttk.Style(self.root).map("Head.TCheckbutton", background=[("active", C["brand"])])

        bar = ttk.Frame(self.root, style="Bg.TFrame", padding=(10, 8))
        bar.pack(fill="x")
        ttk.Button(bar, text="+ Novo chamado", style="Accent.TButton", command=self.new_ticket).pack(side="left")
        ttk.Button(bar, text="Registrar acompanhamento", command=lambda: self._with_sel(self.touch_dialog)
                   ).pack(side="left", padx=(8, 0))
        self.status_mb = ttk.Menubutton(bar, text="Status")
        m = tk.Menu(self.status_mb, tearoff=False)
        for s in STATUSES:
            m.add_command(label=s, command=lambda s=s: self._with_sel(lambda tid: self.set_status(tid, s)))
        self.status_mb["menu"] = m
        self.status_mb.pack(side="left", padx=(8, 0))
        notify_mb = ttk.Menubutton(bar, text="🔔 Notificar a cada")
        notify_mb["menu"] = self._notify_menu(notify_mb, lambda fn: self._with_sel(fn))
        notify_mb.pack(side="left", padx=(8, 0))
        ttk.Button(bar, text="Copiar nº", command=lambda: self._with_sel(lambda tid: self.copy_number(self.store.get(tid)))
                   ).pack(side="left", padx=(8, 0))
        ttk.Button(bar, text="Abrir link", command=lambda: self._with_sel(self.open_link)).pack(side="left", padx=(8, 0))
        ttk.Button(bar, text="⚙", width=3, command=self.settings_dialog).pack(side="right")
        ttk.Button(bar, text="Exportar", command=self.export_csv).pack(side="right", padx=(0, 8))
        ttk.Checkbutton(bar, text="Mostrar fechados", variable=self.show_closed, command=self.refresh
                        ).pack(side="right", padx=(0, 10))

        pane = ttk.PanedWindow(self.root, orient="vertical")
        pane.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        top = ttk.Frame(pane, style="Bg.TFrame")
        self.tree = ttk.Treeview(top, columns=[c[0] for c in COLUMNS], show="headings", selectmode="browse")
        for key, text, width in COLUMNS:
            self.tree.heading(key, text=text, anchor="w")
            self.tree.column(key, width=width, anchor="w", stretch=key == "titulo")
        sb = ttk.Scrollbar(top, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        for tag, bg, fg in (("late", C["late_bg"], C["late_fg"]), ("due", C["warn_bg"], C["warn_fg"]),
                            ("soon", C["soon_bg"], C["ink"]), ("paused", C["surface"], C["paused_fg"])):
            self.tree.tag_configure(tag, background=bg, foreground=fg)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.show_details())
        self.tree.bind("<Double-1>", lambda e: self._with_sel(self.edit_ticket))
        self.tree.bind("<Return>", lambda e: self._with_sel(self.edit_ticket))
        self.tree.bind("<Delete>", lambda e: self._with_sel(self.delete_ticket))
        self.tree.bind("<Button-3>", self._context_menu)
        pane.add(top, weight=3)

        det = ttk.Frame(pane, style="Bg.TFrame", padding=(0, 6, 0, 0))
        self.det_title = ttk.Label(det, text="Selecione um chamado", style="Section.TLabel")
        self.det_title.pack(anchor="w")
        quick = ttk.Frame(det, style="Bg.TFrame")
        quick.pack(fill="x", pady=4)
        self.note = tk.StringVar()
        e = ttk.Entry(quick, textvariable=self.note)
        e.pack(side="left", fill="x", expand=True)
        e.bind("<Return>", lambda ev: self._with_sel(lambda tid: self.touch(tid, self.note.get())))
        ttk.Button(quick, text="Anotar e registrar acompanhamento",
                   command=lambda: self._with_sel(lambda tid: self.touch(tid, self.note.get()))).pack(side="left", padx=(8, 0))
        self.det_text = tk.Text(det, height=7, font=("Segoe UI", 9), relief="solid", bd=1, wrap="word",
                                bg=C["surface"], fg=C["ink"], state="disabled")
        self.det_text.pack(fill="both", expand=True)
        pane.add(det, weight=1)

        self.statusbar = ttk.Label(self.root, text="", style="Hint.TLabel", padding=(12, 0, 12, 6))
        self.statusbar.pack(fill="x")

        self.root.bind("<Control-n>", lambda e: self.new_ticket())
        self.root.bind("<Control-f>", lambda e: ent.focus_set())

    # ----------------------------------------------------------- lista
    def _sel(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _with_sel(self, fn):
        tid = self._sel()
        if tid is None:
            messagebox.showinfo(APP_TITLE, "Selecione um chamado na lista.", parent=self.root)
            return
        fn(tid)

    def refresh(self):
        now = datetime.now()
        cfg = self.store.settings()
        q = self.filter.get().strip().lower()
        tickets = self.store.all(include_closed=self.show_closed.get())
        rows = []
        for t in tickets:
            if q and q not in f"{t.numero} {t.titulo} {t.cliente} {t.status}".lower():
                continue
            follow, flevel = alertas.follow_label(t, cfg, now)
            dead, dlevel = alertas.deadline_label(t, now)
            level = max(flevel, dlevel)
            if flevel == -1:
                tag, order = "paused", 9
            elif dlevel == 2:
                tag, order = "late", 0
            elif flevel == 2 or dlevel == 1:
                tag, order = "due", 1
            elif flevel == 1:
                tag, order = "soon", 2
            else:
                tag, order = "", 3
            key = alertas.followup_at(t, cfg) if flevel != -1 else datetime.max
            rows.append((order, key, t, follow, dead, tag, level))
        rows.sort(key=lambda r: (r[0], r[2].prioridade, r[1]))

        sel = self._sel()
        self.tree.delete(*self.tree.get_children())
        for _o, _k, t, follow, dead, tag, _lvl in rows:
            self.tree.insert("", "end", iid=str(t.id), tags=(tag,) if tag else (),
                             values=(t.numero, t.titulo, t.cliente, t.status, t.prioridade,
                                     alertas.cadence_label(t, cfg), follow, dead))
        if sel is not None and self.tree.exists(str(sel)):
            self.tree.selection_set(str(sel))

        active = [t for t in tickets if not alertas.is_paused(t, cfg)]
        late = sum(1 for r in rows if r[5] == "late")
        due = sum(1 for r in rows if r[5] == "due")
        parts = [f"{len(active)} ativo{'s' if len(active) != 1 else ''}"]
        if late:
            parts.append(f"{late} com prazo estourado")
        if due:
            parts.append(f"{due} para cobrar")
        self.summary.config(text="  ·  ".join(parts))
        work = "dentro" if alertas.in_work_hours(now, cfg) else "fora"
        self.statusbar.config(text=f"Horário de trabalho {cfg['horario_inicio']}–{cfg['horario_fim']} "
                                   f"({work} do horário agora)  ·  dados: {self.store.path}")
        self.show_details()

    def show_details(self):
        tid = self._sel()
        self.det_text.config(state="normal")
        self.det_text.delete("1.0", "end")
        if tid is None or not (t := self.store.get(tid)):
            self.det_title.config(text="Selecione um chamado")
        else:
            self.det_title.config(text=f"{t.numero} — {t.titulo or 'sem título'}")
            if t.notas:
                self.det_text.insert("end", t.notas.strip() + "\n\n")
            for row in self.store.history(tid):
                when = datetime.fromisoformat(row["em"]).strftime("%d/%m %H:%M")
                self.det_text.insert("end", f"{when}   {row['texto']}\n")
        self.det_text.config(state="disabled")

    def _context_menu(self, ev):
        iid = self.tree.identify_row(ev.y)
        if not iid:
            return
        self.tree.selection_set(iid)
        tid = int(iid)
        m = tk.Menu(self.root, tearoff=False)
        m.add_command(label="Registrar acompanhamento…", command=lambda: self.touch_dialog(tid))
        sm = tk.Menu(m, tearoff=False)
        for s in STATUSES:
            sm.add_command(label=s, command=lambda s=s: self.set_status(tid, s))
        m.add_cascade(label="Mudar status", menu=sm)
        m.add_cascade(label="🔔 Notificar cobrança a cada", menu=self._notify_menu(m, lambda fn: fn(tid)))
        am = tk.Menu(m, tearoff=False)
        for label, minutes in (("15 min", 15), ("30 min", 30), ("1 hora", 60), ("2 horas", 120)):
            am.add_command(label=label, command=lambda mi=minutes: self.snooze(tid, mi))
        m.add_cascade(label="Adiar cobrança", menu=am)
        m.add_separator()
        m.add_command(label="Copiar número", command=lambda: self.copy_number(self.store.get(tid)))
        m.add_command(label="Abrir link", command=lambda: self.open_link(tid))
        m.add_command(label="Editar…", command=lambda: self.edit_ticket(tid))
        m.add_separator()
        m.add_command(label="Excluir…", command=lambda: self.delete_ticket(tid))
        m.tk_popup(ev.x_root, ev.y_root)

    # ----------------------------------------------------------- acoes
    def new_ticket(self):
        d = TicketDialog(self.root, self.store)
        self.root.wait_window(d)
        if d.result:
            self.refresh()
            self.tree.selection_set(str(d.result.id))
            self.tree.see(str(d.result.id))

    def edit_ticket(self, tid: int):
        d = TicketDialog(self.root, self.store, self.store.get(tid))
        self.root.wait_window(d)
        if d.result:
            self.refresh()

    def delete_ticket(self, tid: int):
        t = self.store.get(tid)
        if t and messagebox.askyesno(APP_TITLE, f"Excluir o chamado {t.numero} e o histórico dele?", parent=self.root):
            self.store.delete(tid)
            self.refresh()

    def set_status(self, tid: int, status: str):
        t = self.store.get(tid)
        if t and t.status != status:
            t.status = status
            t.ultimo_toque = datetime.now().replace(microsecond=0)   # mudar status conta como acompanhamento
            self.store.save(t)
            self.refresh()
            self._after_action(tid)

    def _notify_menu(self, parent, run) -> tk.Menu:
        """Menu "Notificar cobranca a cada": atalhos, padrao, desligar, personalizar."""
        menu = tk.Menu(parent, tearoff=False)
        for label, minutes in (("15 minutos", 15), ("30 minutos", 30), ("1 hora", 60), ("2 horas", 120),
                               ("4 horas", 240), ("1 dia", 1440)):
            menu.add_command(label=label, command=lambda m=minutes: run(lambda tid: self.set_notify(tid, m)))
        menu.add_separator()
        menu.add_command(label="Padrão da prioridade", command=lambda: run(lambda tid: self.set_notify(tid, None)))
        menu.add_command(label="Não notificar (só prazo)", command=lambda: run(lambda tid: self.set_notify(tid, 0)))
        menu.add_separator()
        menu.add_command(label="Outro intervalo…", command=lambda: run(self.edit_ticket))
        return menu

    def set_notify(self, tid: int, minutes: int | None):
        t = self.store.get(tid)
        if not t or t.cadencia_min == minutes:
            return
        t.cadencia_min = minutes
        self.store.save(t)
        self.refresh()
        cfg = self.store.settings()
        label = alertas.cadence_label(t, cfg)
        nxt = alertas.followup_at(t, cfg)
        extra = "" if nxt == datetime.max else f" · próximo aviso {when_text(max(nxt, datetime.now()))}"
        self.statusbar.config(text=f"{t.numero}: notificar {label}{extra}")

    def touch(self, tid: int, note: str = ""):
        self.store.touch(tid, note)
        self.note.set("")
        self.refresh()
        self._after_action(tid)

    def touch_dialog(self, tid: int, from_alert=None):
        t = self.store.get(tid)
        if not t:
            return
        win = tk.Toplevel(from_alert or self.root)
        win.title(f"Acompanhamento — {t.numero}")
        win.configure(bg=C["bg"], padx=14, pady=12)
        win.attributes("-topmost", True)
        win.transient(from_alert or self.root)
        ttk.Label(win, text="O que foi feito / qual a situação? (opcional)", style="Field.TLabel").pack(anchor="w")
        txt = tk.Text(win, width=56, height=4, font=FONT, relief="solid", bd=1, wrap="word")
        txt.pack(fill="x", pady=6)
        status = tk.StringVar(value=t.status)
        row = ttk.Frame(win, style="Bg.TFrame")
        row.pack(fill="x")
        ttk.Label(row, text="Status", style="Field.TLabel").pack(side="left")
        ttk.Combobox(row, textvariable=status, values=STATUSES, state="readonly", width=22).pack(side="left", padx=6)

        def ok():
            note = txt.get("1.0", "end").strip()
            cur = self.store.get(tid)
            if cur and status.get() != cur.status:
                cur.status = status.get()
                self.store.save(cur)
            self.store.touch(tid, note)
            win.destroy()
            self.refresh()
            self._after_action(tid)

        ttk.Button(row, text="Registrar", style="Accent.TButton", command=ok).pack(side="right")
        win.bind("<Control-Return>", lambda e: ok())
        win.bind("<Escape>", lambda e: win.destroy())
        txt.focus_set()
        win.grab_set()

    def snooze(self, tid: int, minutes: int):
        self.store.snooze(tid, datetime.now().replace(second=0, microsecond=0) + timedelta(minutes=minutes))
        self.refresh()
        self._after_action(tid)

    def _after_action(self, tid: int):
        if self.alert_win and tid in self.alert_win.shown:
            self.alert_win.done(tid)

    def copy_number(self, t: Ticket | None):
        if not t:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(t.numero)
        self.statusbar.config(text=f"Número {t.numero} copiado.")

    def open_link(self, tid: int):
        t = self.store.get(tid)
        if t and t.link:
            webbrowser.open(t.link)
        else:
            messagebox.showinfo(APP_TITLE, "Este chamado não tem link cadastrado.", parent=self.root)

    def settings_dialog(self):
        d = SettingsDialog(self.root, self.store)
        self.root.wait_window(d)
        if d.saved:
            self.refresh()
            self.check_alerts()

    def export_csv(self):
        path = filedialog.asksaveasfilename(
            parent=self.root, title="Exportar chamados", defaultextension=".csv",
            initialfile=f"chamados-{datetime.now():%Y%m%d}.csv", filetypes=[("CSV (Excel)", "*.csv")])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow(["Número", "Título", "Cliente", "Status", "Prioridade", "Prazo", "Criado em",
                        "Último acompanhamento", "Link", "Notas"])
            for t in self.store.all():
                w.writerow([t.numero, t.titulo, t.cliente, t.status, t.prioridade, fmt_when(t.prazo),
                            fmt_when(t.criado_em), fmt_when(t.ultimo_toque), t.link, t.notas])
        self.statusbar.config(text=f"Exportado para {path}")

    def _toggle_top(self):
        self.root.attributes("-topmost", self.topmost.get())
        self.store.save_settings({"sempre_visivel": self.topmost.get()})

    # ----------------------------------------------------------- alertas
    def _tick(self):
        try:
            self.refresh()
            self.check_alerts()
        finally:
            self.root.after(TICK_MS, self._tick)

    def check_alerts(self):
        cfg = self.store.settings()
        now = datetime.now()
        alerts = alertas.due_alerts(self.store.all(include_closed=False), cfg, now)
        win = self.alert_win if self.alert_win and self.alert_win.winfo_exists() else None
        if not alerts and not (win and win.items):
            return
        for a in alerts:          # avisos de prazo valem uma vez: grava ao mostrar
            for pre in a.deadline_marks:
                self.store.mark_deadline_alert(a.ticket.id, pre=pre)
            if a.overdue_mark:
                self.store.mark_deadline_alert(a.ticket.id, overdue=True)
        if win is None:
            win = self.alert_win = AlertWindow(self)
        was_hidden = win.state() == "withdrawn"
        new = win.merge(alerts)
        win.show()
        if new or (was_hidden and alerts):
            if cfg.get("som", True):
                beep()
            flash(win)
            flash(self.root)

    # ----------------------------------------------------------- sair
    def on_close(self):
        cfg = self.store.settings()
        active = [t for t in self.store.all(include_closed=False) if not alertas.is_paused(t, cfg)]
        if active:
            ans = messagebox.askyesnocancel(
                APP_TITLE,
                f"Você tem {len(active)} chamado(s) ativo(s). Fechando o programa, os alertas param.\n\n"
                "Sim = fechar   ·   Não = só minimizar",
                parent=self.root)
            if ans is None:
                return
            if ans is False:
                self.root.iconify()
                return
        self.root.destroy()

    def run(self):
        self.root.mainloop()


# --------------------------------------------------------------------------- #
def _single_instance() -> bool:
    """True se esta e a unica copia aberta; senao traz a outra para frente."""
    if os.name != "nt":
        return True
    k32, u32 = ctypes.windll.kernel32, ctypes.windll.user32
    k32.CreateMutexW(None, False, "Local\\BaseConhecimento.AcompanhamentoChamados")
    if k32.GetLastError() != 183:          # ERROR_ALREADY_EXISTS
        return True
    hwnd = u32.FindWindowW(None, APP_TITLE)
    if hwnd:
        u32.ShowWindow(hwnd, 9)            # SW_RESTORE
        u32.SetForegroundWindow(hwnd)
    return False


def main():
    if not _single_instance():
        return
    if os.name == "nt":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)   # texto nitido em telas com escala
        except Exception:  # noqa: BLE001
            pass
    App(Store()).run()
