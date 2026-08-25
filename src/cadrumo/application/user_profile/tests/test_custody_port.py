"""Architecture contract for the application-owned profile-custody port."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from cadrumo.application.user_profile.custody_ports import (
    bind_profile_custody_port,
    profile_custody_port,
    profile_is_persistence_failure,
)

from ....adapters.persistence.storage import PersistenceError, build_profile_custody_port

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_custody_application_owner_has_no_persistence_imports() -> None:
    owner = Path(__file__).parents[1] / "custody_ports.py"
    tree = ast.parse(owner.read_text(encoding="utf-8"))
    imported = tuple(node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom))

    assert not any(module.startswith("cadrumo.adapters.persistence") for module in imported)


def test_nested_composition_restores_the_exact_outer_port() -> None:
    outer = build_profile_custody_port()
    inner = build_profile_custody_port()

    with bind_profile_custody_port(outer):
        assert profile_custody_port() is outer
        with bind_profile_custody_port(inner):
            assert profile_custody_port() is inner
        assert profile_custody_port() is outer


def test_persistence_failure_classification_preserves_the_exact_storage_family() -> None:
    port = build_profile_custody_port()

    with bind_profile_custody_port(port):
        assert profile_is_persistence_failure(PersistenceError())
        assert not profile_is_persistence_failure(RuntimeError("not a storage failure"))
