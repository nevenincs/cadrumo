"""Smoke checks for the installed Cadrumo package and console-script metadata.

The package import runs in two flavours:

1. **In-process import**: ``import cadrumo`` directly. Catches every
   import-time error reachable from the package's eager
   ``__init__.py`` chain.
2. **Subprocess import**: a fresh Python subprocess proves ``import cadrumo``
   succeeds without relying on the test runner's module cache.
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_cadrumo_package_imports_in_process() -> None:
    """Importing ``cadrumo`` in the test process succeeds without exception.

    The package-level eager imports (the CLI entrypoint, the
    persistence substrate, the registry loaders) all execute as a
    side effect of this import. Any import-time defect anywhere in
    the eager chain raises here.
    """

    from ..core.package_version import PACKAGE_VERSION as __version__

    assert __version__


def test_cadrumo_package_imports_in_subprocess() -> None:
    """Importing ``cadrumo`` in a fresh subprocess succeeds without exception.

    Equivalent to ``python -c "import cadrumo"``. The fresh process has
    no module cache from the test runner, so it exercises the same
    code paths the Cadrumo console-script entrypoint hits on cold
    start. Catches console-script-only regressions where the test
    process's pre-loaded modules mask a real operator failure.
    """

    completed = subprocess.run(
        [sys.executable, "-c", "import cadrumo"],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert completed.returncode == 0, (
        f"fresh-subprocess `import cadrumo` failed:\n  stdout: {completed.stdout!r}\n  stderr: {completed.stderr!r}"
    )


def test_console_scripts_expose_only_the_canonical_cadrumo_commands() -> None:
    """The product distribution ships exactly its canonical human CLI."""
    pyproject = tomllib.loads((_PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["scripts"] == {"aeat": "cadrumo.entrypoints._cli_main:main"}
