"""Ponto de entrada do programa Windows (Base de Conhecimento).

Fluxo:
1. Descobre a pasta de dados (portatil): "dados" ao lado do .exe, ou KB_DATA_DIR.
2. Cria banco + indice de busca se ainda nao existirem.
3. Sobe o servidor local (waitress) em 127.0.0.1 numa porta livre.
4. Abre uma janela dedicada (Edge/Chrome em modo --app); ao fechar, encerra.

A pasta "dados" carrega TODO o estado (banco, arquivos, chave de sessao):
zipar a pasta do programa e compartilhar leva tudo junto.
"""

import ctypes
import logging
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

APP_NAME = "Base de Conhecimento"
PREFERRED_PORT = 5000
PORT_SCAN_RANGE = range(5000, 5051)


# --------------------------------------------------------------------------- #
# Pasta de dados portatil
# --------------------------------------------------------------------------- #
def resolve_data_dir() -> Path:
    env = os.environ.get("KB_DATA_DIR")
    if env:
        return Path(env)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "dados"
    return Path(__file__).resolve().parent / "dados"


def prepare_data_dir(data_dir: Path) -> None:
    (data_dir / "uploads" / "images").mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- #
# Banco
# --------------------------------------------------------------------------- #
def ensure_database(app) -> None:
    from app.db import create_fts, db
    from app.dedup import backfill_fingerprints
    from app.sheets import backfill_sheets

    with app.app_context():
        db.create_all()
        create_fts(db.session)
        for backfill in (backfill_sheets, backfill_fingerprints):
            try:
                backfill()
            except Exception:  # noqa: BLE001 - nao impede o programa de abrir
                db.session.rollback()
                logging.getLogger(__name__).exception("Falha em %s", backfill.__name__)


# --------------------------------------------------------------------------- #
# Servidor
# --------------------------------------------------------------------------- #
def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1", port)) != 0


def _looks_like_us(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/login", timeout=1.5) as resp:
            return "Base de Conhecimento" in resp.read(4096).decode("utf-8", "ignore")
    except Exception:  # noqa: BLE001
        return False


def choose_port() -> tuple[int, bool]:
    """(porta, ja_rodando). ja_rodando=True se outra instancia nossa esta na porta."""
    if not _port_free(PREFERRED_PORT):
        if _looks_like_us(PREFERRED_PORT):
            return PREFERRED_PORT, True
    for port in PORT_SCAN_RANGE:
        if _port_free(port):
            return port, False
    return PREFERRED_PORT, False


def start_server(app, port: int) -> None:
    from waitress import serve

    logging.getLogger("waitress").setLevel(logging.ERROR)
    # Modo servidor (sem janela): escuta a rede local. Modo normal: so localhost.
    host = "0.0.0.0" if os.environ.get("KB_NO_WINDOW") else "127.0.0.1"

    def _run():
        serve(app, host=host, port=port, threads=8, ident=APP_NAME)

    threading.Thread(target=_run, daemon=True, name="kb-server").start()


def wait_until_up(port: int, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/login", timeout=1)
            return True
        except Exception:  # noqa: BLE001
            time.sleep(0.15)
    return False


# --------------------------------------------------------------------------- #
# Janela
# --------------------------------------------------------------------------- #
def _find_browser() -> str | None:
    candidates = []
    for var in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        root = os.environ.get(var)
        if not root:
            continue
        candidates += [
            Path(root) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe",
        ]
    for name in ("msedge", "chrome"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    for path in candidates:
        if path and Path(path).exists():
            return str(path)
    return None


def open_window(url: str) -> bool:
    """Abre uma janela dedicada (modo --app). Bloqueia ate a janela fechar."""
    browser = _find_browser()
    if not browser:
        return False
    profile_root = os.environ.get("LOCALAPPDATA") or str(Path.home())
    profile = Path(profile_root) / "BaseConhecimento" / "janela"
    profile.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.Popen([
            browser,
            f"--app={url}",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--window-size=1280,880",
        ])
    except OSError:
        return False
    proc.wait()
    return True


def open_ui(url: str) -> None:
    if not open_window(url):
        webbrowser.open(url)
        try:
            ctypes.windll.user32.MessageBoxW(
                0,
                f"{APP_NAME} está em execução.\n\n"
                f"Abra no navegador, se ainda não abriu:\n{url}\n\n"
                "Clique em OK para encerrar o programa.",
                APP_NAME,
                0x40,
            )
        except Exception:  # noqa: BLE001
            try:
                input("Pressione Enter para encerrar...")
            except EOFError:
                time.sleep(3600)


def _error_box(message: str) -> None:
    try:
        ctypes.windll.user32.MessageBoxW(0, message, APP_NAME, 0x10)
    except Exception:  # noqa: BLE001
        sys.stderr.write(message + "\n")


# --------------------------------------------------------------------------- #
def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    data_dir = resolve_data_dir()
    os.environ.setdefault("KB_DATA_DIR", str(data_dir))
    prepare_data_dir(data_dir)

    try:
        from app import create_app

        app = create_app()
        ensure_database(app)
    except Exception as exc:  # noqa: BLE001
        _error_box(f"Falha ao iniciar a {APP_NAME}:\n\n{exc}")
        raise

    port, already_running = choose_port()
    url = f"http://127.0.0.1:{port}/"

    if not already_running:
        start_server(app, port)
        if not wait_until_up(port):
            _error_box("O servidor local não respondeu a tempo.")
            sys.exit(1)

    if os.environ.get("KB_SMOKE"):
        # Usado so pelos testes de fumaça: confirma que a UI responde e sai.
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                body = resp.read().decode("utf-8", "ignore")
            (data_dir / ".smoke_body.html").write_text(body, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            (data_dir / ".smoke_error.txt").write_text(repr(exc), encoding="utf-8")
        (data_dir / ".smoke_ok").write_text(str(port), encoding="utf-8")
        os._exit(0)

    if os.environ.get("KB_NO_WINDOW"):
        # Modo servidor: sem janela, escuta a rede local, roda ate ser encerrado.
        try:
            lan_ip = socket.gethostbyname(socket.gethostname())
        except OSError:
            lan_ip = "IP-DO-PC"
        sys.stdout.write(
            f"{APP_NAME} rodando.\n"
            f"  neste PC:        {url}\n"
            f"  na rede local:   http://{lan_ip}:{port}/\n"
        )
        sys.stdout.flush()
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass
        os._exit(0)

    open_ui(url)
    os._exit(0)


if __name__ == "__main__":
    main()
