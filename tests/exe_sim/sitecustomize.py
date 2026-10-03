"""Simulates the packaged .exe for tests: packages the PyInstaller build leaves out can't be
imported. The list is read from the build recipe, so it always matches the real .exe."""
import ast
import importlib.abc
import re
import sys
from pathlib import Path

_SPEC = Path(__file__).resolve().parents[2] / 'DR_Nilesh_Shah_Market_Analysis.spec'


def _excluded():
    try:
        m = re.search(r"excludes=\[(.*?)\]", _SPEC.read_text(encoding='utf-8'), re.S)
        return set(ast.literal_eval('[' + m.group(1) + ']'))
    except Exception:
        return {'sklearn', 'scipy', 'joblib', 'pyarrow'}


EXCLUDED = _excluded()


class _BlockExcluded(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name.split('.')[0] in EXCLUDED:
            raise ModuleNotFoundError(f"No module named '{name}' (left out of the .exe)", name=name)


sys.meta_path.insert(0, _BlockExcluded())
