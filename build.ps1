<#
Gera o programa Windows e o atualizador.
Uso:   .\build.ps1                       (build incremental)
       .\build.ps1 -Clean                (apaga build\ e dist\ antes)
       .\build.ps1 -Version 2026.09.07   (carimba essa versao; padrao = data/hora)

Saidas em dist\:
  BaseConhecimento\               -> instalacao nova (zipe a pasta inteira)
  AtualizarBaseConhecimento.exe   -> atualizacao (mande so este arquivo)

Atualizar uma copia ja instalada: a pessoa copia o AtualizarBaseConhecimento.exe
para dentro da pasta do programa e executa. Ele preserva a pasta "dados".
#>
param(
    [switch]$Clean,
    [string]$Version = (Get-Date -Format "yyyy.MM.dd.HHmm")
)

$ErrorActionPreference = "Stop"
$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { Write-Error "Crie a venv primeiro: python -m venv .venv"; exit 1 }

if ($Clean) {
    Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
}

# O build recria dist\BaseConhecimento do zero. Se o programa gerado antes estiver
# aberto (testando), o banco em dados\ fica travado e o PyInstaller falha: fecha antes.
$distExe = Join-Path (Get-Location) "dist\BaseConhecimento\BaseConhecimento.exe"
$running = Get-Process -Name BaseConhecimento -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -eq $distExe }
if ($running) {
    Write-Host "Fechando o BaseConhecimento.exe aberto a partir de dist\ (PID $($running.Id -join ', '))..." -ForegroundColor Yellow
    $running | Stop-Process -Force
    $running | Wait-Process -Timeout 10 -ErrorAction SilentlyContinue
}

# PyInstaller e pip escrevem progresso no stderr; nao tratar isso como erro.
$ErrorActionPreference = "Continue"

& $py -m pip install -r requirements-build.txt --quiet
if ($LASTEXITCODE -ne 0) { Write-Error "pip install falhou (exit $LASTEXITCODE)"; exit 1 }

# --------------------------------------------------------------------------- #
# 1. O programa
# --------------------------------------------------------------------------- #
& $py -m PyInstaller --noconfirm --clean BaseConhecimento.spec
if ($LASTEXITCODE -ne 0) { Write-Error "PyInstaller falhou (exit $LASTEXITCODE)"; exit 1 }

$out = "dist\BaseConhecimento"

# pasta de dados vazia (o programa cria banco e chave no primeiro uso)
New-Item -ItemType Directory -Force "$out\dados\uploads\images" | Out-Null

if (Test-Path "distrib\LEIA-ME.txt") {
    Copy-Item "distrib\LEIA-ME.txt" "$out\LEIA-ME.txt" -Force
}

# carimbo de versao (usado pelo atualizador para evitar downgrade acidental).
# Sem BOM: o atualizador le como texto simples.
[System.IO.File]::WriteAllText((Join-Path (Resolve-Path $out) "versao.txt"), $Version)

# --------------------------------------------------------------------------- #
# 2. payload.zip = o programa SEM a pasta "dados"
# --------------------------------------------------------------------------- #
$stage = "build\payload"
Remove-Item -Recurse -Force $stage -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $stage | Out-Null

Copy-Item "$out\*" $stage -Recurse -Force
Remove-Item -Recurse -Force "$stage\dados" -ErrorAction SilentlyContinue

Remove-Item -Force "build\payload.zip" -ErrorAction SilentlyContinue
# zip via Python (Compress-Archive falha se o antivirus estiver lendo um arquivo)
& $py scripts\make_zip.py $stage "build\payload.zip"
if ($LASTEXITCODE -ne 0 -or -not (Test-Path "build\payload.zip")) {
    Write-Error "Falha ao gerar build\payload.zip (exit $LASTEXITCODE)"; exit 1
}

# --------------------------------------------------------------------------- #
# 3. O atualizador (arquivo unico, com o payload embutido)
# --------------------------------------------------------------------------- #
& $py -m PyInstaller --noconfirm --clean Atualizador.spec
if ($LASTEXITCODE -ne 0) { Write-Error "PyInstaller (atualizador) falhou (exit $LASTEXITCODE)"; exit 1 }

if (Test-Path "distrib\COMO-ATUALIZAR.txt") {
    Copy-Item "distrib\COMO-ATUALIZAR.txt" "dist\COMO-ATUALIZAR.txt" -Force
}

# --------------------------------------------------------------------------- #
$ErrorActionPreference = "Stop"
Write-Host ""
Write-Host "OK  (versao $Version)" -ForegroundColor Green
Write-Host ""
Write-Host "Instalacao nova:" -ForegroundColor Cyan
Write-Host "  zipe a pasta '$out' inteira e mande."
Write-Host "  Ex.: Compress-Archive -Path $out -DestinationPath BaseConhecimento-$Version.zip -Force"
Write-Host ""
Write-Host "Atualizacao de quem ja usa:" -ForegroundColor Cyan
Write-Host "  mande so 'dist\AtualizarBaseConhecimento.exe' (+ dist\COMO-ATUALIZAR.txt)."
Write-Host "  A pessoa copia o .exe para a pasta do programa e executa. 'dados' e preservada."
