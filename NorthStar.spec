# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = [
    'experimental_search.northstar_runtime',
    'experimental_search.northstar_search',
    'experimental_search.opal_html_v2',
    'ai_manager',
    'fernway_manager',
    'toolbar_tinter',
    'color_extractor',
    'bg_render',
    'dependency_manager',
    'oled_theme',
]
hiddenimports += collect_submodules('experimental_search.search')
hiddenimports += collect_submodules('content')
hiddenimports += collect_submodules('experimental_search.nsindex')


a = Analysis(
    ['NorthStar_v1.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('northstar.ico', '.'),
        ('experimental_search/opal_query_types.json', 'experimental_search'),
        ('quotes.json', '.'),
        ('assets', 'assets'),
    ],
    hiddenimports=hiddenimports,
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
    name='NorthStar',
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
    icon=['northstar.ico'],
)
