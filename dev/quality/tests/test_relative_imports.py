"""Real-behaviour checks for the repository relative-self-import gate."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..._paths import REPO_ROOT
from ..relative_imports import _package_for_path, _scan_file

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_scanner_rejects_absolute_self_imports_for_both_packages(tmp_path: Path) -> None:
    """The detector must bite for each governed package name."""
    source = tmp_path / "sample.py"
    source.write_text("from cadrumo.core import Period\n", encoding="utf-8")
    findings, errors = _scan_file(source, "cadrumo")
    assert errors == []
    assert findings == [(1, "from cadrumo.core import Period")]

    source.write_text("from dev.quality import quiet\n", encoding="utf-8")
    findings, errors = _scan_file(source, "dev")
    assert errors == []
    assert findings == [(1, "from dev.quality import quiet")]


def test_scanner_permits_cross_package_and_relative_imports(tmp_path: Path) -> None:
    """Dev tools may import product code, while self-imports stay relative."""
    source = tmp_path / "sample.py"
    source.write_text("from cadrumo.core import Period\nfrom ..quality import quiet\n", encoding="utf-8")
    findings, errors = _scan_file(source, "dev")
    assert errors == []
    assert findings == []


def test_package_owner_resolves_only_governed_roots() -> None:
    """Target routing covers both package roots and rejects boundary files."""
    repo_root = REPO_ROOT
    assert _package_for_path(repo_root / "src" / "cadrumo" / "core" / "__init__.py") == "cadrumo"
    assert _package_for_path(repo_root / "dev" / "quality" / "relative_imports.py") == "dev"
    assert _package_for_path(repo_root / "tests" / "test_example.py") is None
