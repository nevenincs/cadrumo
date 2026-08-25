"""Fixed-point proof for the active-profile manager projection authority."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import cadrumo.application.operations as operations
import cadrumo.application.user_profile as user_profile

from ..manager_projection import ActiveProfileManagerProjection

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SOURCE_ROOT = Path(__file__).resolve().parents[3]


def test_manager_projection_has_one_direct_public_home() -> None:
    assert ActiveProfileManagerProjection.__module__ == "cadrumo.application.user_profile.manager_projection"
    assert "ActiveProfileManagerProjection" not in user_profile.__all__
    assert not hasattr(user_profile, "ActiveProfileManagerProjection")


def test_retired_callback_authority_is_absent() -> None:
    assert not hasattr(operations, "ManagerAction")
    assert not (_SOURCE_ROOT / "application" / "operations" / "_profile_manager.py").exists()
    assert not (_SOURCE_ROOT / "entrypoints" / "cli" / "_config" / "_manager_actions.py").exists()

    declarations: list[tuple[Path, str]] = []
    roots = (
        _SOURCE_ROOT / "application" / "operations",
        _SOURCE_ROOT / "entrypoints" / "cli" / "_config",
        _SOURCE_ROOT / "entrypoints" / "tui",
    )
    for root in roots:
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            declarations.extend(
                (path, node.name)
                for node in ast.walk(tree)
                if isinstance(node, ast.ClassDef) and node.name.startswith("ManagerAction")
            )
    assert declarations == []
