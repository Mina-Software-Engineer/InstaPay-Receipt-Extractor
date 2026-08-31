# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules("google.genai")

analysis = Analysis(
    ["app.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("ic_edita_logo.png", "."),
        ("ic_whatsapp.png", "."),
        ("ic_facebook.png", "."),
        ("ic_linkedin.png", "."),
    ],
    hiddenimports=hiddenimports + [
        "win32com",
        "win32com.client",
        "pythoncom",
        "pywintypes",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "pytest_qt"],
    noarchive=False,
)

pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="InstaPayReceiptRegister",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon="ic_edita_logo.ico",
)
