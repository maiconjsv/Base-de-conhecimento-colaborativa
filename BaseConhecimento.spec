# PyInstaller spec - gera dist/BaseConhecimento/ (pasta com tudo dentro).
#   pyinstaller --noconfirm BaseConhecimento.spec
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = (
    collect_submodules("markdown")
    + collect_submodules("waitress")
    + [
        "sqlalchemy.dialects.sqlite",
        "sqlalchemy.sql.default_comparator",
        "xlrd",  # planilhas .xls antigas (importado sob demanda em app/sheets.py)
    ]
)

datas = [
    ("app/templates", "app/templates"),
    ("app/static", "app/static"),
]

a = Analysis(
    ["desktop.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pytest", "PyInstaller"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BaseConhecimento",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="BaseConhecimento",
)
