# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

# Dynamically gather hidden imports for local modules
hidden_modules = [
    'youface.locales',
    'youface.app_context',
    'youface.conda',
    'youface.core',
    'youface.state_manager',
    'youface.program',
    'youface.args',
    'youface.jobs',
    'youface.filesystem',
    'youface.logger',
    'youface.translator',
    'youface.process_manager',
    'youface.inference_manager',
    'youface.execution',
    'youface.exit_helper',
    'youface.time_helper',
    'youface.common_helper',
    'youface.types',
    'youface.metadata',
]

# Processors
processors_dir = os.path.join('youface', 'processors', 'modules')
if os.path.exists(processors_dir):
    for entry in os.listdir(processors_dir):
        entry_path = os.path.join(processors_dir, entry)
        if os.path.isdir(entry_path) and not entry.startswith('__'):
            hidden_modules.append(f'youface.processors.modules.{entry}')
            hidden_modules.append(f'youface.processors.modules.{entry}.core')
            hidden_modules.append(f'youface.processors.modules.{entry}.locales')

# Layouts
layouts_dir = os.path.join('youface', 'uis', 'layouts')
if os.path.exists(layouts_dir):
    for entry in os.listdir(layouts_dir):
        if entry.endswith('.py') and not entry.startswith('__'):
            name = entry[:-3]
            hidden_modules.append(f'youface.uis.layouts.{name}')

hidden_imports_list = [
    'uvicorn',
    'sqlalchemy',
    'sqlalchemy.ext.declarative',
    'sqlalchemy.orm',
    'fastapi',
    'fastapi.staticfiles',
    'pydantic',
    'multipart',
    'onnxruntime',
    'cv2',
    'numpy',
    'scipy',
    'tqdm',
    'sqlite3',
] + hidden_modules

a = Analysis(
    ['run_api.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('youface/processors/modules', 'youface/processors/modules'),
        ('youface/uis/layouts', 'youface/uis/layouts'),
        ('frontend/out', 'frontend/out'),
    ],
    hiddenimports=hidden_imports_list,
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
    name='youface-app',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
