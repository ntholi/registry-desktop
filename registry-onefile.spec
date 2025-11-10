# -*- mode: python ; coding: utf-8 -*-

import tomllib
from pathlib import Path

pyproject_path = Path('pyproject.toml')
with open(pyproject_path, 'rb') as f:
    pyproject = tomllib.load(f)
    version = pyproject.get('project', {}).get('version', 'unknown')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('base/nav/menu.json', 'base/nav'),
        ('pyproject.toml', '.'),
        ('images', 'images'),
    ],
    hiddenimports=[
        'wx',
        'wx._core',
        'wx._html',
        'wx.lib.agw.customtreectrl',
        'sqlalchemy',
        'sqlalchemy.dialects.sqlite',
        'bs4',
        'selenium',
        'requests',
        'google.auth',
        'google.oauth2',
        'google_auth_oauthlib',
        'google_auth_httplib2',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=f'registry-desktop-{version}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
