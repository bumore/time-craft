# -*- mode: python ; coding: utf-8 -*-
import sys
import os

block_cipher = None

# 项目路径
project_dir = os.path.abspath(os.getcwd())
scripts_dir = os.path.join(project_dir, 'scripts')
app_dir = os.path.join(project_dir, 'app')

a = Analysis(
    [os.path.join(app_dir, 'main.py')],
    pathex=[app_dir, scripts_dir],
    binaries=[],
    datas=[
        (os.path.join(project_dir, 'data', 'state.json'), 'data'),
    ],
    hiddenimports=[
        'pystray',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'input_hook',
        'active_monitor',
        'tray',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='TimeCraft',
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
