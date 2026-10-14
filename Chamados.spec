# PyInstaller spec - gera dist/AcompanhamentoChamados.exe (arquivo unico, sem console).
# O build.ps1 copia o .exe para dentro de dist\BaseConhecimento\ (mesma pasta de dados).
#   pyinstaller --noconfirm Chamados.spec

a = Analysis(
    ["chamados_main.py"],
    pathex=[],
    binaries=[],
    datas=[("app/static/favicon.png", "app/static")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # so tkinter + sqlite: nada do sistema web
    excludes=["flask", "flask_sqlalchemy", "flask_login", "flask_wtf", "sqlalchemy", "werkzeug",
              "jinja2", "waitress", "lxml", "PIL", "pypdf", "docx", "pptx", "openpyxl", "xlrd",
              "markdown", "pytest", "PyInstaller"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="AcompanhamentoChamados",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=None,
)
