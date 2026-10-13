"""Compacta uma pasta em .zip (usado pelo build.ps1 para gerar o payload.zip).

Substitui o Compress-Archive do PowerShell, que falha quando o antivirus esta
examinando um arquivo recem-copiado ("being used by another process"). Aqui,
cada arquivo preso e tentado de novo por alguns segundos antes de desistir.

Uso: python scripts/make_zip.py <pasta> <destino.zip>
"""

import sys
import time
import zipfile
from pathlib import Path

RETRIES = 20
WAIT_SECONDS = 0.5


def _read_with_retry(path: Path) -> bytes:
    for attempt in range(RETRIES):
        try:
            return path.read_bytes()
        except PermissionError:
            if attempt == RETRIES - 1:
                raise
            time.sleep(WAIT_SECONDS)
    raise AssertionError("unreachable")


def main(src: str, dest: str) -> int:
    root = Path(src)
    if not root.is_dir():
        print(f"Pasta nao encontrada: {root}", file=sys.stderr)
        return 1
    out = Path(dest)
    tmp = out.with_suffix(".zip.tmp")
    count = 0
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                zf.writestr(path.relative_to(root).as_posix(), _read_with_retry(path))
                count += 1
    tmp.replace(out)
    print(f"{out}: {count} arquivo(s)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))
