"""Exercise the standalone interpreter without any application dependencies."""

import builtins
import importlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path


def require(condition: bool, message: str) -> None:
    """Keep checks enabled under optimized Python as well."""
    if not condition:
        raise AssertionError(message)


root = Path(sys.prefix)
manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
layout = manifest["layout"]["paths"]
packages = root / layout["packages"]
require(packages.is_dir(), "Missing site-packages directory")
require(packages.resolve() in [Path(path).resolve() for path in sys.path], "Missing site-packages import path")
with zipfile.ZipFile(root / layout["stdlib"]) as library:
    require("site.pyc" in library.namelist(), "Missing site in python.zip")
require("site" in sys.modules and not sys.flags.no_site, "Normal site initialization is disabled")
require(bool(sys.flags.isolated and sys.flags.no_user_site), "External Python isolation changed")
for name in ("exit", "quit", "help"):
    require(callable(getattr(builtins, name, None)), f"Missing standard helper: {name}")
for name in ("ssl", "sqlite3", "ctypes", "bz2", "lzma", "multiprocessing", "venv"):
    importlib.import_module(name)
for helper in ("exit", "quit"):
    for arguments, expected in (("", 0), ("17", 17)):
        result = subprocess.run(
            [sys.executable, "-i", "-q"],
            input=f"{helper}({arguments})\nraise RuntimeError('did not exit')\n",
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        require(result.returncode == expected and "Traceback" not in result.stderr, f"{helper} failed: {result.stderr}")
result = subprocess.run(
    [sys.executable, "-S", "-c", "import sys; assert sys.flags.no_site and 'site' not in sys.modules"],
    text=True,
    capture_output=True,
    timeout=30,
    check=False,
)
require(result.returncode == 0, f"Explicit -S failed: {result.stderr}")
sys.stdout.write(f"Standalone Python passed: {sys.executable}\n")
