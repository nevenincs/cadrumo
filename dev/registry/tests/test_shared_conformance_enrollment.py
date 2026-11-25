"""The run-wide conformance enrollment is keyed on every development-registry file the verification reads."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from .shared_conformance_enrollment import enrollment_inputs

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_EXERCISE = str(filing_year_envelope().horizon)


def test_the_enrollment_key_covers_maps_profiles_vectors_and_modules_but_not_tests(tmp_path: Path) -> None:
    registry = tmp_path / "registry"
    planted = {
        "module": registry / "filing_export_conformance_enrollment.py",
        "nested_module": registry / "pipeline" / "tree_check.py",
        "semantic_map": registry / "mappings" / "modelo_303" / _EXERCISE / "semantic_map.toml",
        "render_profile": registry / "render_profiles" / "modelo_303" / _EXERCISE / "profile.toml",
        "vector": registry / "conformance_vectors" / "modelo_200.toml",
    }
    excluded = {
        "test_module": registry / "tests" / "test_enrollment.py",
        "nested_test": registry / "pipeline" / "tests" / "test_tree_check.py",
        "bytecode": registry / "__pycache__" / "module.cpython-313.pyc",
        "unread_data": registry / "notes" / "scratch.toml",
    }
    for path in (*planted.values(), *excluded.values()):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x = 1\n")

    inputs = set(enrollment_inputs(registry))

    assert set(planted.values()) <= inputs
    assert inputs.isdisjoint(excluded.values())


def test_the_committed_enrollment_inputs_name_the_real_verification_data() -> None:
    inputs = enrollment_inputs()

    for tree in ("mappings", "render_profiles", "conformance_vectors"):
        assert any(tree in path.parts for path in inputs), tree
    assert any(path.name == "filing_export_conformance_enrollment.py" for path in inputs)
