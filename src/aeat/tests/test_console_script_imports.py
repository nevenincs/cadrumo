"""Structural gate: ``python -c "import aeat"`` must always succeed.

The 2026-05-19 disaster recovery (Ruling 7) traced the cold-start
10-minute silent hang to a stale ``aeat.domain.iva`` import that
crashed every ``aeat`` console-script invocation after the registry
validation completed. The crash was masked by a compatibility shim
at ``aeat.domain.iva.__init__`` that re-exported from
``aeat.domain.iva``; the shim violated the project's no-shim mandate
and was retired in the same commit as this gate landed.

This test enforces the contract that no rename, no module retire,
and no symbol relocation may re-introduce a top-level import error
on the ``aeat`` package. Future agents who delete a module without
sweeping its callers fail this gate at commit time.

The gate runs in two flavours:

1. **In-process import**: ``import aeat`` directly. Catches every
   import-time error reachable from the package's eager
   ``__init__.py`` chain.
2. **Subprocess import**: a fresh Python subprocess running
   ``python -c "import aeat"``. Catches the console-script-only
   class of failure where module caching in the test process masks
   a regression a real operator would hit on cold start.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_aeat_package_imports_in_process() -> None:
    """Importing ``aeat`` in the test process succeeds without exception.

    The package-level eager imports (the CLI entrypoint, the
    persistence substrate, the registry loaders) all execute as a
    side effect of this import. Any import-time defect anywhere in
    the eager chain raises here.
    """

    __import__("aeat")


def test_aeat_package_imports_in_subprocess() -> None:
    """Importing ``aeat`` in a fresh subprocess succeeds without exception.

    Equivalent to ``python -c "import aeat"``. The fresh process has
    no module cache from the test runner, so it exercises the same
    code paths the ``aeat`` console-script entrypoint hits on cold
    start. Catches console-script-only regressions where the test
    process's pre-loaded modules mask a real operator failure.
    """

    completed = subprocess.run(
        [sys.executable, "-c", "import aeat"],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert completed.returncode == 0, (
        f"fresh-subprocess `import aeat` failed:\n  stdout: {completed.stdout!r}\n  stderr: {completed.stderr!r}"
    )
