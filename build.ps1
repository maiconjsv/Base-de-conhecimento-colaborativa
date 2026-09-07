<#
Gera o programa Windows em dist\BaseConhecimento\.
Uso:   .\build.ps1            (build incremental)
       .\build.ps1 -Clean     (apaga build\ e dist\ antes)
Depois: zipe a pasta dist\BaseConhecimento inteira e compartilhe.
#>
param([switch]$Clean)

$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { Write-Error "Crie a venv primeiro: python -m venv .venv"; exit 1 }

if ($Clean) {
    Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
}

# PyInstaller e pip escrevem progresso no stderr; nao tratar isso como erro.
$ErrorActionPreference = "Continue"

& $py -m pip install -r requirements-build.txt --quiet
if ($LASTEXITCODE -ne 0) { Write-Error "pip install falhou (exit $LASTEXITCODE)"; exit 1 }

& $py -m PyInstaller --noconfirm --clean BaseConhecimento.spec
if ($LASTEXITCODE -ne 0) { Write-Error "PyInstaller falhou (exit $LASTEXITCODE)"; exit 1 }

$out = "dist\BaseConhecimento"

# pasta de dados vazia (o programa cria banco e chave no primeiro uso)
New-Item -ItemType Directory -Force "$out\dados\uploads\images" | Out-Null

if (Test-Path "distrib\LEIA-ME.txt") {
    Copy-Item "distrib\LEIA-ME.txt" "$out\LEIA-ME.txt" -Force
}

Write-Host ""
Write-Host "OK -> $out" -ForegroundColor Green
Write-Host "Teste: $out\BaseConhecimento.exe"
Write-Host "Distribuir: zipe a pasta '$out' inteira (o zip leva os dados em dados\)."
