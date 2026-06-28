"""Coverage guards for registry-backed modelo calculation parity."""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core.resources import bundled_path
from .. import load_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_TEST_ROOT = Path(__file__).parent


def test_formula_bearing_modelos_have_constructs_and_model_specific_tests() -> None:
    modelos, _ = load_registry_tree(_REGISTRY_ROOT)

    violations: list[str] = []
    for modelo in sorted(modelos, key=lambda item: item.id):
        formula_count = sum(len(revision.formulas) for revision in modelo.revisions.values())
        if formula_count == 0:
            continue
        construct_count = sum(len(revision.constructs) for revision in modelo.revisions.values())
        if construct_count == 0:
            violations.append(f"modelo {modelo.id}: has formulas but no registry constructs")
        test_path = _TEST_ROOT / f"test_modelo_{modelo.id}_registry.py"
        if not test_path.is_file():
            violations.append(f"modelo {modelo.id}: has formulas but no model-specific registry test")

    assert violations == []
