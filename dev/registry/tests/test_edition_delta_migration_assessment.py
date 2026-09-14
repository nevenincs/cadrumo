"""Focused regression tests for migration measurement and report coverage."""

from __future__ import annotations

from pathlib import Path

import pytest

import dev.registry.edition_delta_migration as migration
from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]
_MODELO_100 = REPO_ROOT / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "modelos" / "100"


def test_canonical_shape_reader_keeps_singletons_and_keyed_members_distinct() -> None:
    singleton = {"status": "complete", "gaps": []}
    keyed = [{"id": "a", "nested": {"enabled": False}}, {"id": "b"}]

    assert migration._members({"completeness_manifest": singleton}, "completeness_manifest", singleton=True) == (
        singleton,
    )
    assert migration._members({"formulas": keyed}, "formulas") == tuple(keyed)
    assert migration._members({"formulas": singleton}, "formulas") is None


def test_typed_comparison_preserves_false_zero_absence_empty_and_array_order() -> None:
    assert not migration._typed_equal(False, 0)
    assert not migration._typed_equal({}, [])
    assert not migration._typed_equal(["a", "b"], ["b", "a"])
    assert not migration._typed_equal({"present": []}, {})
    assert migration._typed_equal({"present": [], "enabled": False}, {"present": [], "enabled": False})


def test_nested_values_have_stable_leaf_counting_and_locations() -> None:
    leaves = migration._leaf_values({"provider": {"options": {"enabled": False}}, "order": ["a", "b"]})

    assert leaves == {
        ("provider", "options", "enabled"): False,
        ("order",): ["a", "b"],
    }


def test_live_modelo_100_assessment_covers_singleton_scalars_and_is_read_only() -> None:
    before = migration._file_fingerprints(_MODELO_100)

    assessment = migration.assess_migration_state(_MODELO_100)

    completeness = [row for row in assessment.by_revision_family if row["family"] == "completeness_manifest"]
    scalars = [row for row in assessment.by_revision_family if row["family"] == "$scalars"]
    assert len(completeness) == len(scalars) == 6
    assert all(row["authored_payload_fields"] > 0 for row in completeness)
    assert all(row["authored_payload_fields"] > 0 for row in scalars)
    assert assessment.inputs_stable
    assert assessment.input_fingerprints == before == migration._file_fingerprints(_MODELO_100)
    assert assessment.redundant_overrides > 0
    assert not assessment.minimal


def test_changed_captured_input_blocks_minimality(monkeypatch: pytest.MonkeyPatch) -> None:
    original = migration._file_fingerprints
    calls = 0

    def changing(path: Path) -> tuple[dict[str, str], ...]:
        nonlocal calls
        calls += 1
        captured = tuple(dict(item) for item in original(path))
        if calls == 1:
            return captured
        return (*captured, {"path": "mutated", "sha256": "changed"})

    monkeypatch.setattr(migration, "_file_fingerprints", changing)

    assessment = migration.assess_migration_state(_MODELO_100)

    assert not assessment.inputs_stable
    assert any(item["reason"] == "inputs_changed_during_assessment" for item in assessment.blocked_work)
    assert not assessment.minimal
