# PyInstaller build recipe for DR. NILESH SHAH'S MARKET ANALYSIS
#
# Easiest: double-click build_exe.bat (builds and installs into this folder).
# Manually:
#     python -m PyInstaller DR_Nilesh_Shah_Market_Analysis.spec --noconfirm
#     then copy everything in "dist\DR Nilesh Shah Market Analysis\" into this folder.
#
# One-folder build (the .exe plus an _internal folder): starts in ~6-10 s. A single-file
# build was ~25 s per launch because it unpacks everything to a temp folder every time.

from PyInstaller.utils.hooks import collect_submodules, copy_metadata

hiddenimports = (
    # local modules imported inside try/except or functions
    ['pattern_recognition', 'daily_report', 'corporate_actions',
     'corporate_actions_engine', 'market_data', 'backtest', 'scheduled_report', 'app_paths', 'score_history',
     'scoring', 'ui_theme', 'mpl_toolkits.mplot3d',
     'tkinter.simpledialog']
    # Windows Credential Manager backend for the email password
    + collect_submodules('keyring.backends')
)

a = Analysis(
    ['dr_shah_analysis.py'],
    pathex=[],
    binaries=[],
    datas=[('logo_new.png', '.')] + copy_metadata('keyring'),
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Not needed by the app: tools installed on this PC for other projects. Leaving them out
    # makes the .exe much smaller and faster to start.
    excludes=['sklearn', 'scipy', 'joblib', 'IPython', 'jupyter', 'notebook', 'pytest',
              'streamlit', 'flask', 'altair', 'pyarrow', 'torch', 'tensorflow', 'PyQt5', 'PyQt6',
              'PySide2', 'PySide6', 'ruff', 'uvicorn'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DR Nilesh Shah Market Analysis',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,          # windowed app: no black console window
    icon='app_icon.ico',
)

coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='DR Nilesh Shah Market Analysis')
