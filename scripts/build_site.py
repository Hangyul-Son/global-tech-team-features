#!/usr/bin/env python3
"""Copy only public static assets to an ignored deployment directory."""
from pathlib import Path
import shutil
ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / '_site'
if DEST.is_symlink():
    raise SystemExit('Refusing to write through a symlink at _site')
DEST.mkdir(exist_ok=True)
for name in ['index.html', 'research.html', 'chinese.html', 'articles', 'css', 'js', 'data']:
    source, target = ROOT / name, DEST / name
    if source.is_dir():
        shutil.copytree(source, target, dirs_exist_ok=True)
    else:
        shutil.copy2(source, target)
print('Static site prepared in _site; no external dependencies or build toolchain required.')
