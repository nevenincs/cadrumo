"""Detector teeth for live zero-target unconsumed-export coverage."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..unconsumed_export_coverage import find_unconsumed

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_EXPORTED = '__all__ = ["widget"]\n\n\ndef widget() -> None: ...\n'


def _tree(tmp_path: Path, **modules: str) -> Path:
    root = tmp_path / "pkg"
    root.mkdir()
    for name, source in modules.items():
        (root / f"{name}.py").write_text(source, encoding="utf-8")
    return root


def _unused(root: Path, module: str, name: str) -> set[tuple[str, str]]:
    return {(f"{root.name}/{module}.py", name)}


def test_an_exact_unused_export_without_a_production_importer_is_reported(tmp_path: Path) -> None:
    root = _tree(tmp_path, lonely=_EXPORTED)
    assert [(finding.path, finding.name) for finding in find_unconsumed(root, _unused(root, "lonely", "widget"))] == [
        ("lonely.py", "widget"),
    ]


def test_a_production_importer_consumes_the_export(tmp_path: Path) -> None:
    root = _tree(tmp_path, lonely=_EXPORTED, user="from .lonely import widget\n")
    assert find_unconsumed(root, _unused(root, "lonely", "widget")) == ()


def test_an_unreadable_module_refuses_to_claim_zero(tmp_path: Path) -> None:
    root = _tree(tmp_path, lonely=_EXPORTED, broken="def nope(:\n")
    with pytest.raises(RuntimeError, match=r"broken\.py"):
        find_unconsumed(root, _unused(root, "lonely", "widget"))
