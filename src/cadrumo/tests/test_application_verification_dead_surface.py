"""Structural gate for the deleted standalone application verification surface."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from ..core.directory_scan import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CADRUMO_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT = _CADRUMO_ROOT.parents[1]
_DEAD_MODULE = ".".join(("cadrumo", "application", "verification"))
_DEAD_PATH = "/".join(("application", "verification"))
_DEAD_VERB = "_".join(("verify", "declaracion"))


def test_application_verification_package_and_import_are_absent() -> None:
    package = _CADRUMO_ROOT.joinpath("application", "verification")

    assert not package.exists()
    assert importlib.util.find_spec(_DEAD_MODULE) is None


def test_dead_application_verification_strings_have_no_consumers() -> None:
    searched_roots = (_CADRUMO_ROOT, _REPO_ROOT / "docs" / "api")
    suffixes = {".py", ".rst", ".toml"}
    needles = (_DEAD_MODULE, _DEAD_PATH, _DEAD_VERB)
    consumers: list[str] = []

    for root in searched_roots:
        for path in scan_directory(root, pattern="*", recursive=True):
            if path.suffix not in suffixes:
                continue
            text = path.read_text(encoding="utf-8")
            if any(needle in text for needle in needles):
                consumers.append(path.relative_to(_REPO_ROOT).as_posix())

    assert consumers == []


def test_registry_has_no_deleted_application_consumer() -> None:
    registry_root = _CADRUMO_ROOT / "_data" / "registry" / "aeat" / "modelos"
    consumer_declaration = f'consumer = "{_DEAD_MODULE}"'
    consumers = [
        path.relative_to(_REPO_ROOT).as_posix()
        for path in scan_directory(registry_root, pattern="*.toml", recursive=True)
        if consumer_declaration in path.read_text(encoding="utf-8")
    ]

    assert consumers == []
