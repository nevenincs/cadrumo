"""Gate: vaultspec-rag is a dev-box tool, never a docs-work dependency.

Operator directive (2026-07-13, docs-terminology-search): a non-dev
environment must execute all docs work — the Sphinx build, the Pagefind
record injection, the generated reference surfaces, the preprocess hook —
without vaultspec-rag installed. The rag package lives in the
contributor-only dependency group and is reached from dev tooling ONLY
through function-local imports (the sweep's reindex helper, the extractor
tests' chunking probes) or external CLI invocations, so importing the
docs-work modules must never pull it in.

The gate runs a child interpreter with a meta-path blocker that makes any
``vaultspec_rag`` import raise, then imports every module on the docs-work
path. A future top-level ``import vaultspec_rag`` anywhere on that path
fails this gate loudly instead of breaking non-dev environments silently.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

from cadrumo.core import scan_directory

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_REPO_ROOT = REPO_ROOT

#: Every module the docs build, the docs gates, and the preprocess hook load.
_DOCS_WORK_MODULES: Final[tuple[str, ...]] = (
    "dev.docs.build",
    "dev.docs.serve",
    "dev.docs.env_reference",
    "dev.docs.cli_reference",
    "dev.docs.pagefind_inject",
    "dev.docs.terminology",
    "dev.docs.preprocess",
    "dev.docs.preprocess.hook",
)

_BLOCKER_TEMPLATE: Final[str] = """
import importlib.abc
import importlib.machinery
import sys


class _Blocked(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "vaultspec_rag" or fullname.startswith("vaultspec_rag."):
            raise ImportError(
                "vaultspec_rag imported on the docs-work path: " + fullname
            )
        return None


sys.meta_path.insert(0, _Blocked())
import importlib

for name in {modules!r}:
    importlib.import_module(name)
print("DOCS-WORK-RAG-FREE")
"""


def test_docs_work_modules_import_without_vaultspec_rag() -> None:
    """Every docs-work module imports with vaultspec_rag made unimportable."""
    script = _BLOCKER_TEMPLATE.format(modules=list(_DOCS_WORK_MODULES))
    result = subprocess.run(  # noqa: S603 - fixed interpreter, repo-internal script
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
        env=None,
    )
    assert result.returncode == 0, f"docs-work import failed under the vaultspec_rag blocker:\n{result.stderr[-2000:]}"
    assert "DOCS-WORK-RAG-FREE" in result.stdout


def _production_python_files() -> tuple[Path, ...]:
    """Every Python module under the production package."""
    return scan_directory(_REPO_ROOT / "src" / "cadrumo", pattern="*.py", recursive=True)


def test_production_package_never_imports_vaultspec_rag() -> None:
    """No module under src/cadrumo references vaultspec_rag at all."""
    files = _production_python_files()
    # A survivor scan reports the same clean result over the real package and
    # over a path that does not exist, so the corpus size is the only thing
    # separating "nothing references it" from "nothing was read".
    assert len(files) > 500, f"expected the production package, scanned only {len(files)} module(s)"
    offenders = [
        str(path.relative_to(_REPO_ROOT))
        for path in files
        if "vaultspec_rag" in path.read_text(encoding="utf-8", errors="ignore")
    ]
    assert not offenders, f"src/cadrumo references vaultspec_rag: {offenders}"


def test_the_production_scan_detects_a_reference_when_one_exists(tmp_path: Path) -> None:
    """The detection itself works: a file carrying the token is found.

    Without this the gate proves only that its corpus is large, not that
    reading it would surface a real reference.
    """
    (tmp_path / "clean.py").write_text("import json\n", encoding="utf-8")
    (tmp_path / "offending.py").write_text("import vaultspec_rag\n", encoding="utf-8")
    found = [
        path.name
        for path in scan_directory(tmp_path, pattern="*.py", recursive=True)
        if "vaultspec_rag" in path.read_text(encoding="utf-8", errors="ignore")
    ]
    assert found == ["offending.py"]
