"""IA local: controla o llama-server (llama.cpp) e conversa com ele.

Tudo roda na propria maquina: o motor e um executavel que acompanha o programa
(`llama\\llama-server.exe`) e o modelo e um arquivo .gguf na pasta `modelos\\`.
Nada e enviado para a internet.

Ciclo de vida do motor:
- liga na primeira pergunta (carregar o modelo leva alguns segundos);
- desliga sozinho depois de LLM_IDLE_MINUTES sem uso, para devolver a memoria;
- no Windows, fica preso a um "job object": se o programa fechar (ou for
  encerrado a forca), o motor morre junto e nao fica ocupando RAM.

A conversa usa a API do llama-server compativel com OpenAI
(/v1/chat/completions, com streaming), entao trocar por outro provedor no
futuro (Copilot, Gemini, ...) e so trocar o endereco.
"""

import atexit
import ctypes
import json
import logging
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

PREFERRED_MODEL = "gemma-3-4b"      # parte do nome do .gguf preferido
CTX_SIZE = 8192
START_TIMEOUT = 240                 # segundos para carregar o modelo
IDLE_MINUTES = 10
MIN_RAM_GB = 6.0                    # abaixo disso, avisa que pode ficar lento


class LLMError(Exception):
    """Falha da IA local, com mensagem para mostrar ao usuario."""


# --------------------------------------------------------------------------- #
# Onde ficam o motor e o modelo
# --------------------------------------------------------------------------- #
def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def server_path() -> Path | None:
    env = os.environ.get("KB_LLM_SERVER")
    candidates = [Path(env)] if env else []
    base = _base_dir()
    candidates += [base / "llama" / "llama-server.exe", base / "vendor" / "llama" / "llama-server.exe"]
    return next((p for p in candidates if p.is_file()), None)


def local_models_dir() -> Path | None:
    """Pasta local do usuario, fora do OneDrive: %LOCALAPPDATA%\\BaseConhecimento\\modelos.

    Para quem tem o programa numa pasta sincronizada (OneDrive): o modelo de 2,5 GB
    fica aqui e nao vai para a nuvem.
    """
    root = os.environ.get("LOCALAPPDATA")
    return Path(root) / "BaseConhecimento" / "modelos" if root else None


def models_dirs() -> list[Path]:
    env = os.environ.get("KB_MODELS_DIR")
    base = _base_dir()
    dirs = [Path(env)] if env else []
    dirs += [base / "modelos"]
    if local_models_dir():
        dirs.append(local_models_dir())
    return dirs + [base / "vendor" / "modelos"]


def model_path() -> Path | None:
    """O .gguf a usar: o preferido (Gemma 3 4B) ou o primeiro que houver."""
    found = []
    for d in models_dirs():
        if d.is_dir():
            found += [p for p in d.glob("*.gguf") if "mmproj" not in p.name.lower()]
    if not found:
        return None
    preferred = [p for p in found if PREFERRED_MODEL in p.name.lower()]
    return sorted(preferred or found, key=lambda p: p.name)[0]


def memory_gb() -> tuple[float, float]:
    """(RAM total, RAM livre) em GB. (0, 0) se nao der para saber."""
    if os.name != "nt":
        return 0.0, 0.0

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    st = MEMORYSTATUSEX()
    st.dwLength = ctypes.sizeof(st)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
        return 0.0, 0.0
    return st.ullTotalPhys / 1024**3, st.ullAvailPhys / 1024**3


# --------------------------------------------------------------------------- #
# "Job object": o motor morre junto com o programa
# --------------------------------------------------------------------------- #
def _kill_on_close_job():
    if os.name != "nt":
        return None
    k32 = ctypes.windll.kernel32

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [(n, ctypes.c_ulonglong) for n in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class BASIC_LIMIT(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", ctypes.c_ulong), ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", ctypes.c_ulong),
            ("Affinity", ctypes.c_size_t), ("PriorityClass", ctypes.c_ulong),
            ("SchedulingClass", ctypes.c_ulong),
        ]

    class EXTENDED_LIMIT(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", BASIC_LIMIT), ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    k32.CreateJobObjectW.restype = ctypes.c_void_p
    job = k32.CreateJobObjectW(None, None)
    if not job:
        return None
    info = EXTENDED_LIMIT()
    info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    k32.SetInformationJobObject.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong]
    if not k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
        return None
    return job


def _assign_to_job(job, proc) -> None:
    if not job:
        return
    k32 = ctypes.windll.kernel32
    k32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    k32.AssignProcessToJobObject(job, ctypes.c_void_p(int(proc._handle)))


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# --------------------------------------------------------------------------- #
# Motor
# --------------------------------------------------------------------------- #
class LocalEngine:
    def __init__(self):
        self._lock = threading.RLock()
        self._proc: subprocess.Popen | None = None
        self._port = 0
        self._model: Path | None = None
        self._last_used = 0.0
        self._active = 0
        self._job = None
        self._watcher: threading.Thread | None = None
        self.log_path: Path | None = None   # definido pela app (pasta de dados)

    # ----- estado
    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def status(self) -> dict:
        server, model = server_path(), model_path()
        total, free = memory_gb()
        reason = ""
        if server is None:
            reason = "O motor da IA (llama-server) não está instalado nesta cópia do programa."
        elif model is None:
            reason = ("Nenhum modelo de IA encontrado. Coloque o arquivo gemma-3-4b-it-Q4_K_M.gguf "
                      f"na pasta 'modelos' do programa ({_base_dir() / 'modelos'})"
                      + (f" ou, se o programa estiver no OneDrive, em {local_models_dir()} "
                         "(pasta local, não sincroniza)" if local_models_dir() else "") + ".")
        warning = ""
        need_gb = (model.stat().st_size / 1024**3 + 1.0) if model else 0   # modelo + contexto
        if not reason and total and total < MIN_RAM_GB:
            warning = (f"Este computador tem {total:.0f} GB de RAM; a IA pode ficar lenta "
                       "ou travar outros programas enquanto responde.")
        elif not reason and not self.running and free and free < need_gb:
            warning = (f"Pouca memória livre agora ({free:.1f} GB; a IA usa cerca de {need_gb:.1f} GB). "
                       "Ela funciona, mas a primeira resposta pode demorar: feche programas pesados se puder.")
        return {
            "available": not reason,
            "reason": reason,
            "warning": warning,
            "running": self.running,
            "model": model.stem if model else "",
            "model_gb": round(model.stat().st_size / 1024**3, 1) if model else 0,
            "ram_total_gb": round(total, 1),
            "ram_free_gb": round(free, 1),
        }

    # ----- ligar / desligar
    def ensure_running(self) -> None:
        with self._lock:
            if self.running:
                self._last_used = time.time()
                return
            server, model = server_path(), model_path()
            if server is None or model is None:
                raise LLMError(self.status()["reason"])

            self._port = _free_port()
            cmd = [
                str(server), "-m", str(model),
                "-c", str(CTX_SIZE), "-np", "1",
                "--host", "127.0.0.1", "--port", str(self._port),
            ]
            log = open(self.log_path, "w", encoding="utf-8", errors="replace") if self.log_path else subprocess.DEVNULL
            flags = 0x08000000 if os.name == "nt" else 0          # CREATE_NO_WINDOW
            logger.info("Ligando a IA local: %s", model.name)
            self._proc = subprocess.Popen(
                cmd, cwd=str(server.parent), stdout=log, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, creationflags=flags,
            )
            if self._job is None:
                self._job = _kill_on_close_job()
            _assign_to_job(self._job, self._proc)
            self._model = model
            self._wait_ready()
            self._last_used = time.time()
            self._start_watcher()

    def _wait_ready(self) -> None:
        deadline = time.time() + START_TIMEOUT
        url = f"http://127.0.0.1:{self._port}/health"
        while time.time() < deadline:
            if self._proc.poll() is not None:
                tail = self._log_tail()
                self._proc = None
                raise LLMError("A IA local não conseguiu iniciar." + (f"\n\n{tail}" if tail else ""))
            try:
                with urllib.request.urlopen(url, timeout=2) as r:
                    if r.status == 200:
                        return
            except (urllib.error.URLError, OSError):
                pass                       # ainda carregando (503) ou subindo
            time.sleep(0.5)
        self.stop()
        raise LLMError("A IA local demorou demais para carregar o modelo.")

    def _log_tail(self, lines: int = 6) -> str:
        try:
            text = self.log_path.read_text(encoding="utf-8", errors="replace") if self.log_path else ""
        except OSError:
            return ""
        return "\n".join(text.strip().splitlines()[-lines:])

    def stop(self) -> None:
        with self._lock:
            proc, self._proc = self._proc, None
            if proc and proc.poll() is None:
                logger.info("Desligando a IA local.")
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()

    def _start_watcher(self) -> None:
        if self._watcher and self._watcher.is_alive():
            return

        def watch():
            while True:
                time.sleep(30)
                with self._lock:
                    if not self.running:
                        return
                    idle = time.time() - self._last_used
                    if self._active == 0 and idle > IDLE_MINUTES * 60:
                        self.stop()
                        return

        self._watcher = threading.Thread(target=watch, daemon=True, name="kb-ia-ociosa")
        self._watcher.start()

    # ----- conversa
    def stream_chat(self, messages: list[dict], *, max_tokens: int = 800, temperature: float = 0.2):
        """Gera a resposta em pedacos de texto (streaming)."""
        self.ensure_running()
        body = json.dumps({
            "messages": messages, "stream": True, "temperature": temperature,
            "max_tokens": max_tokens, "cache_prompt": True,
        }).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{self._port}/v1/chat/completions", data=body,
            headers={"Content-Type": "application/json"},
        )
        with self._lock:
            self._active += 1
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                for raw in resp:
                    line = raw.decode("utf-8", "replace").strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        delta = json.loads(data)["choices"][0].get("delta", {})
                    except (ValueError, KeyError, IndexError):
                        continue
                    if delta.get("content"):
                        self._last_used = time.time()
                        yield delta["content"]
        except (urllib.error.URLError, OSError) as exc:
            raise LLMError(f"A IA local parou de responder ({exc}).") from exc
        finally:
            with self._lock:
                self._active -= 1
                self._last_used = time.time()


engine = LocalEngine()
atexit.register(engine.stop)


# --------------------------------------------------------------------------- #
# Prompt
# --------------------------------------------------------------------------- #
SYSTEM_PROMPT = (
    "Você é o assistente da Base de Conhecimento de uma equipe de suporte. "
    "Responda em português do Brasil, de forma direta e organizada (use listas quando ajudar). "
    "Use SOMENTE as informações dos trechos numerados que o usuário enviar. "
    "Depois de cada informação, cite o número do trecho entre colchetes, por exemplo [1] ou [2][3]. "
    "Se a resposta não estiver nos trechos, diga claramente que não encontrou essa informação "
    "na documentação e não tente adivinhar. Nunca invente telefones, e-mails, nomes, endereços, "
    "números de circuito ou passos de procedimento."
)
# Quanto texto vai para a IA. No CPU, ler o texto e o que mais demora (~70 tokens/s
# num i5 de 11a geracao): ~3.200 caracteres ficam em ~1.000 tokens, ~15 s.
MAX_CONTEXT_CHARS = 3200
MAX_PASSAGE_CHARS = 1200
MAX_AI_PASSAGES = 4


HISTORY_TURNS = 2            # perguntas anteriores da conversa que a IA ve
HISTORY_ANSWER_CHARS = 500   # de cada resposta anterior (o resto deixaria lento)


def build_messages(question: str, passages: list[dict], history: list[dict] | None = None) -> list[dict]:
    """Os trechos ja vem do mais ao menos relevante; corta no limite de tamanho.

    `history`: [{"q", "a"}] das ultimas perguntas, para entender continuacoes
    ("e o telefone dela?"). So os trechos da pergunta atual vao junto.
    """
    parts, used = [], 0
    for i, p in enumerate(passages[:MAX_AI_PASSAGES], 1):
        text = p["plain"]
        if len(text) > MAX_PASSAGE_CHARS:
            text = text[:MAX_PASSAGE_CHARS].rsplit(" ", 1)[0] + " …"
        block = f"[{i}] {p['label']}\n{text}"
        if used + len(block) > MAX_CONTEXT_CHARS and parts:
            break
        parts.append(block)
        used += len(block)
    user = "Trechos da documentação:\n\n" + "\n\n".join(parts) + f"\n\nPergunta: {question}"
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for turn in (history or [])[-HISTORY_TURNS:]:
        messages.append({"role": "user", "content": turn["q"]})
        messages.append({"role": "assistant", "content": turn["a"][:HISTORY_ANSWER_CHARS]})
    messages.append({"role": "user", "content": user})
    return messages
