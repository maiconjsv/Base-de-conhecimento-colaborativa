# PyInstaller spec - gera dist/AtualizarBaseConhecimento.exe (arquivo unico).
# A versao nova do programa vai embutida como payload.zip (criado pelo build.ps1
# ANTES de rodar este spec). Distribuicao da atualizacao = so este .exe.
#   pyinstaller --noconfirm Atualizador.spec

a = Analysis(
    ["updater.py"],
    pathex=[],
    binaries=[],
    datas=[("build/payload.zip", ".")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pytest", "PyInstaller", "flask", "sqlalchemy",
              "lxml", "PIL", "waitress", "markdown"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="AtualizarBaseConhecimento",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    icon=None,
)
