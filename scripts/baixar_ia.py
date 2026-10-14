"""Baixa o motor de IA local (llama.cpp) e o modelo para a pasta vendor/.

Uso (na raiz do projeto):
    .\\.venv\\Scripts\\python.exe scripts\\baixar_ia.py            # motor + modelo
    .\\.venv\\Scripts\\python.exe scripts\\baixar_ia.py --so-motor # so o llama-server

Depois disso:
- em desenvolvimento (run.py) o sistema ja encontra vendor/llama e vendor/modelos;
- o build.ps1 copia o motor para dist\\BaseConhecimento\\llama\\ e, com -ComModelo,
  o modelo para dist\\BaseConhecimento\\modelos\\.

Os downloads sao retomaveis (arquivo .part) e pulados se ja estiverem completos.
"""

import argparse
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "vendor"

# Versao fixa do llama.cpp (build CPU x64), para todo mundo usar a mesma.
LLAMA_BUILD = "b11617"
LLAMA_URL = (
    "https://github.com/ggml-org/llama.cpp/releases/download/"
    f"{LLAMA_BUILD}/llama-{LLAMA_BUILD}-bin-win-cpu-x64.zip"
)

# Gemma 3 4B instruct, quantizado Q4_K_M (~2,5 GB). Licenca: Gemma Terms of Use.
MODEL_FILE = "gemma-3-4b-it-Q4_K_M.gguf"
MODEL_URL = f"https://huggingface.co/ggml-org/gemma-3-4b-it-GGUF/resolve/main/{MODEL_FILE}"


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    have = part.stat().st_size if part.exists() else 0
    req = urllib.request.Request(url, headers={"User-Agent": "BaseConhecimento"})
    if have:
        req.add_header("Range", f"bytes={have}-")
    with urllib.request.urlopen(req, timeout=60) as resp:
        if have and resp.status != 206:      # servidor nao retomou: recomeca
            have = 0
        total = have + int(resp.headers.get("Content-Length") or 0)
        mode = "ab" if have else "wb"
        done, last = have, -1
        with open(part, mode) as fh:
            while True:
                block = resp.read(1024 * 1024)
                if not block:
                    break
                fh.write(block)
                done += len(block)
                pct = int(done * 100 / total) if total else 0
                if pct != last and pct % 5 == 0:
                    print(f"  {dest.name}: {pct}% ({done / 1e6:,.0f} MB)", flush=True)
                    last = pct
    part.replace(dest)


def get_engine() -> None:
    target = VENDOR / "llama"
    if (target / "llama-server.exe").exists():
        print(f"Motor ja presente em {target}")
        return
    zip_path = VENDOR / f"llama-{LLAMA_BUILD}.zip"
    print(f"Baixando o motor llama.cpp {LLAMA_BUILD}...")
    download(LLAMA_URL, zip_path)
    shutil.rmtree(target, ignore_errors=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(target)
    # alguns pacotes vem com uma subpasta: traz o conteudo para vendor/llama
    if not (target / "llama-server.exe").exists():
        found = next(target.rglob("llama-server.exe"), None)
        if found is None:
            sys.exit("llama-server.exe nao encontrado no pacote baixado.")
        for item in found.parent.iterdir():
            shutil.move(str(item), str(target / item.name))
    zip_path.unlink(missing_ok=True)
    (target / "VERSAO.txt").write_text(LLAMA_BUILD, encoding="utf-8")
    print(f"Motor pronto em {target}")


def get_model() -> None:
    dest = VENDOR / "modelos" / MODEL_FILE
    if dest.exists():
        print(f"Modelo ja presente em {dest}")
        return
    print(f"Baixando o modelo {MODEL_FILE} (~2,5 GB)...")
    download(MODEL_URL, dest)
    print(f"Modelo pronto em {dest}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--so-motor", action="store_true", help="baixa so o llama-server")
    args = ap.parse_args()
    get_engine()
    if not args.so_motor:
        get_model()


if __name__ == "__main__":
    main()
