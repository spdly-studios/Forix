# forix.spec

from pathlib import Path
from PyInstaller.utils.hooks import collect_all

block_cipher = None
HERE = Path().resolve()

qt_datas, qt_binaries, qt_hiddenimports = collect_all('PyQt6')

a = Analysis(
    ['main.py'],
    pathex=[str(HERE)],

    binaries=qt_binaries,

    datas=[
        ('assets', 'assets'),
        ('config.py', '.'),
    ] + qt_datas,

    hiddenimports=[
        'sqlalchemy.dialects.sqlite',
        'sqlalchemy.sql.default_comparator',
        'watchdog.observers.winapi',
        'watchdog.observers.read_directory_changes',
        'pkg_resources.py2_compat',
        'Levenshtein',
    ] + qt_hiddenimports,

    excludes=[
        'matplotlib', 'numpy', 'pandas',
        'tkinter', 'PyQt5', 'wx',
        'IPython', 'notebook', 'jupyter',
        'openai', 'anthropic',
        'test', 'unittest', 'doctest',
    ],

    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,

    name='Forix',
    console=False,
    icon='assets/forix.ico',
    upx=False,   # safer for PyQt
)