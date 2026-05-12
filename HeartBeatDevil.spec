# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec: build on each OS separately (Mac on macOS, Windows on Windows).
# Output: dist/HeartBeatDevil/ with HeartBeatDevil(.exe) + _internal/

import os

block_cipher = None

root = os.path.abspath(os.path.join(os.path.dirname(SPEC)))

a = Analysis(
	[os.path.join(root, "3DrageBait.py")],
	pathex=[root],
	binaries=[],
	datas=[(os.path.join(root, "models"), "models")],
	hiddenimports=[
		"OpenGL",
		"OpenGL.GL",
		"OpenGL.GLU",
		"OpenGL.arrays",
		"OpenGL.platform",
		"pygame",
		"firebase_admin",
		"google.auth",
		"google.auth.transport.requests",
		"cv2",
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
	[],
	exclude_binaries=True,
	name="HeartBeatDevil",
	debug=False,
	bootloader_ignore_signals=False,
	strip=False,
	upx=True,
	# Use console=True while testing; switch to False to hide the terminal on Windows.
	console=True,
	disable_windowed_traceback=False,
	argv_emulation=False,
	target_arch=None,
	codesign_identity=None,
	entitlements_file=None,
)

coll = COLLECT(
	exe,
	a.binaries,
	a.zipfiles,
	a.datas,
	strip=False,
	upx=True,
	upx_exclude=[],
	name="HeartBeatDevil",
)
