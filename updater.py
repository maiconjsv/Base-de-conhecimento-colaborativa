"""Atualizador da Base de Conhecimento (executavel unico).

Como usar (para quem recebe a atualizacao):
1. Copie este arquivo para dentro da pasta do programa - a mesma onde estao
   "BaseConhecimento.exe" e a pasta "dados".
2. Feche o programa se estiver aberto.
3. Execute este arquivo (duplo clique).

O que ele faz:
- Encerra o programa se ainda estiver rodando.
- Faz uma copia de seguranca da pasta "dados" em "_backup\\dados-<data>".
- Substitui os arquivos do programa (BaseConhecimento.exe e _internal\\) pela
  versao nova, que vem embutida neste executavel.
- NUNCA toca em "dados\\", ".env" nem "secret.key".
- Se algo falhar no meio da troca, desfaz o que ja tinha mexido.
- Depois que a versao nova esta no lugar, apagar os arquivos antigos e so
  "faxina": se o Windows/OneDrive segurar algum arquivo, ele fica para tras e e
  apagado na proxima atualizacao, sem desfazer nada.
- No fim, reabre o programa.

A versao nova vem embutida aqui como "payload.zip" (gerado pelo build.ps1).
"""

import ctypes
import os
import shutil
import stat
import subprocess
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path

APP_NAME = "Base de Conhecimento"
APP_EXE = "BaseConhecimento.exe"
PAYLOAD_NAME = "payload.zip"
VERSION_FILE = "versao.txt"

# Nunca substituidos nem apagados pela atualizacao.
PRESERVE = {"dados", ".env", "secret.key", "_backup", "_update_tmp"}
STAGING_PREFIX = "_update_tmp"
KEEP_BACKUPS = 2

MB_OK = 0x40
MB_ICONWARNING = 0x30
MB_ICONERROR = 0x10
MB_YESNO = 0x04
IDYES = 6


def log(msg: str = "") -> None:
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "ascii"
        print(msg.encode(enc, "replace").decode(enc, "replace"), flush=True)


def msgbox(text: str, flags: int = MB_OK) -> int:
    try:
        return ctypes.windll.user32.MessageBoxW(0, text, APP_NAME, flags)
    except Exception:  # noqa: BLE001
        return 0


def pause_and_exit(code: int) -> None:
    log()
    try:
        input("Pressione Enter para fechar esta janela...")
    except EOFError:
        time.sleep(15)
    sys.exit(code)


def resource_path(name: str) -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / name
    return Path(__file__).resolve().parent / name


def install_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def read_version(path: Path) -> str:
    try:
        # utf-8-sig ja remove o BOM; o strip extra cobre BOM no meio/duplo.
        raw = path.read_text(encoding="utf-8-sig")
        return raw.replace("﻿", "").strip()
    except OSError:
        return ""


def retry(fn, *, tries: int = 12, delay: float = 0.5):
    """Repete uma operacao de arquivo enquanto o Windows a bloqueia."""
    last = None
    for _ in range(tries):
        try:
            return fn()
        except PermissionError as exc:  # arquivo ainda em uso
            last = exc
            time.sleep(delay)
        except OSError as exc:
            last = exc
            time.sleep(delay)
    if last:
        raise last


def _clear_readonly(func, path, _exc):
    """onexc do rmtree: tira o 'somente leitura' e tenta de novo."""
    try:
        os.chmod(path, stat.S_IWRITE)
    except OSError:
        pass
    func(path)


def remove_path(path: Path, *, tries: int = 20, delay: float = 0.5) -> bool:
    """Apaga arquivo/pasta insistindo (OneDrive e antivirus seguram arquivos
    recem-mexidos por alguns segundos). Devolve False se nao conseguiu."""
    for _ in range(tries):
        if not os.path.lexists(path):
            return True
        try:
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path, onexc=_clear_readonly)
            else:
                try:
                    os.chmod(path, stat.S_IWRITE)
                except OSError:
                    pass
                path.unlink()
            return True
        except OSError:
            time.sleep(delay)
    return not os.path.lexists(path)


def sweep_leftovers(root: Path) -> None:
    """Faxina de tentativas anteriores: *.old, *.old-*, *.falhou-*, _update_tmp*."""
    for item in root.iterdir():
        n = item.name
        if n.endswith(".old") or ".old-" in n or ".falhou-" in n or n.startswith(STAGING_PREFIX):
            if remove_path(item, tries=4):
                log(f"  removido resto de atualizacao anterior: {n}")
            else:
                log(f"  (nao consegui remover '{n}' agora; fica para a proxima)")


# --------------------------------------------------------------------------- #
# Encerrar o programa em execucao
# --------------------------------------------------------------------------- #
def _powershell(cmd: str) -> str:
    try:
        return subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
            capture_output=True, text=True, timeout=20,
        ).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def stop_app(root: Path) -> None:
    exe_path = str((root / APP_EXE).resolve()).lower()
    killed = False

    # 1) So os processos que rodam a PARTIR desta pasta.
    pids = _powershell(
        "Get-CimInstance Win32_Process -Filter \"Name='%s'\" | "
        "Where-Object { $_.ExecutablePath } | "
        "ForEach-Object { if ($_.ExecutablePath.ToLower() -eq '%s') "
        "{ $_.ProcessId } }" % (APP_EXE, exe_path.replace("'", "''"))
    )
    for pid in pids.split():
        if pid.strip().isdigit():
            subprocess.run(["taskkill", "/PID", pid.strip(), "/F", "/T"],
                           capture_output=True)
            killed = True

    # 2) Janela dedicada (Edge/Chrome em modo --app com o nosso perfil).
    _powershell(
        "Get-CimInstance Win32_Process -Filter "
        "\"Name='msedge.exe' OR Name='chrome.exe'\" | "
        "Where-Object { $_.CommandLine -like '*BaseConhecimento*janela*' } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force "
        "-ErrorAction SilentlyContinue }"
    )

    # 3) Se nao achou pelo caminho, tenta pelo nome (menos preciso).
    if not killed:
        subprocess.run(["taskkill", "/IM", APP_EXE, "/F", "/T"],
                       capture_output=True)

    time.sleep(2.0)  # deixa o Windows liberar os arquivos


# --------------------------------------------------------------------------- #
# Backup da pasta de dados
# --------------------------------------------------------------------------- #
def backup_data(root: Path) -> Path | None:
    dados = root / "dados"
    if not dados.is_dir():
        return None
    backup_root = root / "_backup"
    backup_root.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = backup_root / f"dados-{stamp}"
    log(f"  copiando 'dados' para {dest.relative_to(root)} ...")
    shutil.copytree(dados, dest)

    antigas = sorted(p for p in backup_root.glob("dados-*") if p.is_dir())
    for p in antigas[:-KEEP_BACKUPS]:
        shutil.rmtree(p, ignore_errors=True)
        log(f"  backup antigo removido: {p.name}")
    return dest


# --------------------------------------------------------------------------- #
# Troca dos arquivos do programa
# --------------------------------------------------------------------------- #
def apply_update(root: Path, staging: Path) -> list[str]:
    """Move cada item de 'staging' para 'root', preservando os dados.

    Fase 1 (troca): cada item atual vira '<nome>.old-<stamp>' e o novo entra no
    lugar. Se algo falhar aqui, desfaz tudo e levanta o erro.
    Fase 2 (faxina): apaga os '.old-*'. Falha aqui NAO desfaz nada: a versao nova
    ja esta completa; o que sobrar e apagado na proxima atualizacao.

    Devolve os nomes que nao deu para apagar na faxina.
    """
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    moves: list[tuple[Path, Path | None]] = []  # (destino, antigo renomeado ou None)
    try:
        for item in sorted(staging.iterdir()):
            name = item.name
            if name in PRESERVE:
                continue
            dest = root / name
            old = None
            if os.path.lexists(dest):
                old = root / f"{name}.old-{stamp}"
                retry(lambda d=dest, o=old: os.rename(d, o))
            moves.append((dest, old))
            retry(lambda s=item, d=dest: shutil.move(str(s), str(d)))
            log(f"  atualizado: {name}")
    except Exception:
        log("  ERRO durante a troca - desfazendo...")
        rollback(root, moves, stamp)
        raise

    # ---- fase 2: faxina (a atualizacao ja deu certo)
    leftovers = []
    for _dest, old in moves:
        if old is not None and not remove_path(old):
            leftovers.append(old.name)
            log(f"  (nao consegui apagar '{old.name}' agora; sera apagado na proxima atualizacao)")
    return leftovers


def rollback(root: Path, moves, stamp: str) -> None:
    """Desfaz a fase 1: tira o item novo do caminho e devolve o antigo."""
    for dest, old in reversed(moves):
        try:
            if os.path.lexists(dest):
                failed = root / f"{dest.name}.falhou-{stamp}"
                retry(lambda d=dest, f=failed: os.rename(d, f))
                remove_path(failed, tries=4)
            if old is not None:
                retry(lambda o=old, d=dest: os.rename(o, d))
        except OSError as exc:
            log(f"  !! nao consegui restaurar '{dest.name}': {exc}")


def relaunch(root: Path) -> None:
    if os.environ.get("KB_UPDATER_NO_RELAUNCH"):
        return
    exe = root / APP_EXE
    if exe.exists():
        try:
            subprocess.Popen([str(exe)], cwd=str(root))
        except OSError:
            pass  # sem relaunch automatico; a pessoa abre o programa na mao


# --------------------------------------------------------------------------- #
def main() -> None:
    log(f"Atualizador da {APP_NAME}")
    log("=" * 40)

    root = install_dir()
    log(f"Pasta do programa: {root}")

    # sem o .exe mas com a pasta de dados: instalacao que ficou pela metade,
    # o atualizador consegue recolocar o programa
    if not (root / APP_EXE).exists() and not (root / "dados").is_dir():
        msgbox(
            "Este atualizador precisa estar DENTRO da pasta do programa.\n\n"
            f"Copie '{Path(sys.executable).name}' para a mesma pasta onde esta "
            f"'{APP_EXE}' (e a pasta 'dados') e execute de novo.",
            MB_ICONWARNING,
        )
        log(f"\n'{APP_EXE}' nao encontrado nesta pasta. Nada foi alterado.")
        pause_and_exit(1)

    payload = resource_path(PAYLOAD_NAME)
    if not payload.exists():
        msgbox("Este atualizador esta corrompido (sem conteudo embutido).",
               MB_ICONERROR)
        pause_and_exit(1)

    log("\nLimpando restos de atualizacoes anteriores...")
    sweep_leftovers(root)

    staging = root / f"{STAGING_PREFIX}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    staging.mkdir()

    log("\n[1/4] Abrindo a versao nova...")
    with zipfile.ZipFile(payload) as zf:
        zf.extractall(staging)

    nova = read_version(staging / VERSION_FILE)
    atual = read_version(root / VERSION_FILE)
    log(f"  versao instalada: {atual or '(desconhecida)'}")
    log(f"  versao nova:      {nova or '(desconhecida)'}")
    if nova and atual and nova <= atual:
        if msgbox(
            f"A versao instalada ({atual}) e igual ou mais nova que a "
            f"deste atualizador ({nova}).\n\nAtualizar mesmo assim?",
            MB_YESNO | MB_ICONWARNING,
        ) != IDYES:
            shutil.rmtree(staging, ignore_errors=True)
            log("\nCancelado pelo usuario. Nada foi alterado.")
            pause_and_exit(0)

    log("\n[2/4] Encerrando o programa (se estiver aberto)...")
    stop_app(root)

    log("\n[3/4] Backup da pasta 'dados'...")
    try:
        dest = backup_data(root)
        log(f"  backup: {dest}" if dest else "  (pasta 'dados' ainda nao existe)")
    except OSError as exc:
        msgbox(f"Nao consegui copiar a pasta 'dados'.\n\n{exc}\n\n"
               "A atualizacao foi cancelada para nao arriscar seus dados.",
               MB_ICONERROR)
        shutil.rmtree(staging, ignore_errors=True)
        pause_and_exit(1)

    log("\n[4/4] Trocando os arquivos do programa...")
    try:
        apply_update(root, staging)
    except OSError as exc:
        if "onedrive" in str(root).lower():
            hint = ("O programa esta numa pasta do OneDrive, que trava arquivos enquanto "
                    "sincroniza. Tente de novo em alguns minutos, ou mova a pasta para "
                    "fora do OneDrive (ex.: 'C:\\BaseConhecimento').")
        else:
            hint = ("Se o programa estiver instalado em 'C:\\Program Files', mova a pasta "
                    "para outro lugar (ex.: 'C:\\BaseConhecimento') ou rode este "
                    "atualizador como administrador.")
        msgbox(
            f"A atualizacao falhou e foi desfeita.\n\n{exc}\n\n"
            f"Seus dados estao intactos. {hint}",
            MB_ICONERROR,
        )
        remove_path(staging, tries=4)
        pause_and_exit(1)

    remove_path(staging, tries=4)

    log("\nPronto! Reabrindo o programa...")
    relaunch(root)
    msgbox(
        f"{APP_NAME} atualizada com sucesso"
        + (f" para a versao {nova}." if nova else ".")
        + "\n\nSeus documentos e usuarios continuam iguais.\n"
        "Uma copia de seguranca ficou em '_backup'.",
        MB_ICONWARNING if not nova else MB_OK,
    )
    log("Concluido.")
    pause_and_exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        msgbox(f"Erro inesperado no atualizador:\n\n{exc!r}\n\n"
               "Seus dados nao foram alterados.", MB_ICONERROR)
        pause_and_exit(1)
