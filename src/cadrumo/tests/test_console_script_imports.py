"""Structural gate for the Cadrumo package hard cut.

A prior disaster-recovery traced a cold-start
10-minute silent hang to a stale ``cadrumo.domain.iva`` import that
crashed every Cadrumo console-script invocation after the registry
validation completed. The crash was masked by a compatibility shim
at ``cadrumo.domain.iva.__init__`` that re-exported from
``cadrumo.domain.iva``; the shim violated the project's no-shim mandate
and was retired in the same commit as this gate landed.

These tests enforce both sides of the rename contract: the canonical
``cadrumo`` package must import successfully, while the retired ``aeat``
product root must fail instead of resolving through an alias or shim.

The gate runs in two flavours:

1. **In-process import**: ``import cadrumo`` directly. Catches every
   import-time error reachable from the package's eager
   ``__init__.py`` chain.
2. **Subprocess imports**: a fresh Python subprocess proves
   ``import cadrumo`` succeeds and ``import aeat`` fails without aliases.
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

    __import__("cadrumo")


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


def test_retired_aeat_package_fails_in_subprocess() -> None:
    """The retired product root does not resolve through an alias or shim."""
    completed = subprocess.run(
        [sys.executable, "-c", "import aeat"],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert completed.returncode != 0, (
        "fresh-subprocess `import aeat` unexpectedly succeeded; the hard cut forbids compatibility aliases and shims"
    )


def test_retired_aeat_package_root_is_absent_from_the_source_tree() -> None:
    """The checkout contains no package or module that could restore ``import aeat``."""
    source_root = _PROJECT_ROOT / "src"

    assert not (source_root / "aeat").exists()
    assert not (source_root / "aeat.py").exists()


def test_console_scripts_expose_only_the_canonical_cadrumo_commands() -> None:
    """The product distribution ships exactly its canonical human CLI."""
    pyproject = tomllib.loads((_PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["scripts"] == {"aeat": "cadrumo.entrypoints._cli_main:main"}
