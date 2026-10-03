"""Exercise the assembled distribution using its own interpreter."""

import importlib.metadata
import json
import subprocess
import sys
from pathlib import Path

import pikepdf
from win32com.shell import shell


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


require(bool(shell.__file__), "COM extension did not load")
with pikepdf.Pdf.new() as document:
    document.add_blank_page()
require(
    importlib.metadata.version("cadrumo") == importlib.metadata.version("cadrumo-data-official"),
    "Official cohort mismatch",
)
require(
    importlib.metadata.version("cadrumo") == importlib.metadata.version("cadrumo-data-manuals"),
    "Manual cohort mismatch",
)
require(bool(sys.flags.isolated and not sys.flags.site_import), "Interpreter is not isolated")
require(sys.version_info[:2] == (3, 13), "Wrong CPython minor version")
child = subprocess.check_output(
    [sys.executable, "-c", "import json,sys; print(json.dumps([sys.executable,sys.flags.isolated]))"], text=True
)
executable, isolated = json.loads(child)
require(Path(executable) == Path(sys.executable) and isolated == 1, "Child interpreter escaped package")
sys.stdout.write(f"CADRUMO {importlib.metadata.version('cadrumo')}: {sys.executable}\n")
