"""Focused regression tests for migration measurement and report coverage."""

from __future__ import annotations

from pathlib import Path

import pytest

import dev.registry.edition_delta_migration as migration
from dev._paths import REPO_ROOT
from dev.registry.tests.test_restated_family_merge import _build_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]
_MODELO_100 = REPO_ROOT / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "modelos" / "100"


def _positive(row: object) -> bool:
    return isinstance(row, int) and row > 0


def _fields(finding: dict[str, object] | object) -> list[str]:
    if not isinstance(finding, dict):
        return []
    value = finding.get("fields")
    return [item for item in value if isinstance(item, str)] if isinstance(value, list | tuple) else []


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


def test_only_converter_failure_roots_are_reassessed_against_the_adjacent_revision() -> None:
    independent = {"predecessor": {"none": {"reason": "different territorial applicability"}}}
    technical = {"predecessor": {"none": {"reason": "migration predecessor_row_without_lineage"}}}

    assert not migration._technical_root(independent)
    assert migration._technical_root(technical)


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
    assert all(_positive(row["authored_payload_fields"]) for row in completeness)
    assert all(_positive(row["authored_payload_fields"]) for row in scalars)
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


def test_real_loader_assessment_distinguishes_restatement_from_inheritance(tmp_path: Path) -> None:
    modelo = _build_modelo(tmp_path)

    assessment = migration.assess_migration_state(modelo)

    formulas = next(
        row for row in assessment.by_revision_family if row["revision"] == "2025" and row["family"] == "formulas"
    )
    loaded = migration.load_modelo_directory(modelo)
    inherited_formula = next(item for item in loaded.revisions["2024"].formulas if item.id == "modelo-999-cuota")
    inherited_fields = sum(
        1
        for path in migration._leaf_values(migration._model_value(inherited_formula))
        if path and path[0] not in migration._STRUCTURAL_FIELDS
    )
    exact = [
        item
        for item in assessment.unresolved_duplication
        if item["revision"] == "2025" and item["family"] == "formulas" and item["member"] == "modelo-999-base"
    ]
    assert _positive(formulas["authored_payload_fields"])
    assert formulas["inherited_payload_fields"] == inherited_fields
    assert _positive(formulas["redundant_overrides"])
    assert exact and "expression.literal" in _fields(exact[0])


@pytest.mark.parametrize(("literal", "redundant"), [("0", True), ("7", False)])
def test_nested_family_override_detector_is_independent_and_exact(
    tmp_path: Path, literal: str, redundant: bool
) -> None:
    declaration = (
        '[[revisions."2025".family_overrides]]\n'
        'family = "formulas"\n'
        'selector = { revision = "2024", id = "modelo-999-cuota" }\n'
        f'fields = {{ expression = {{ literal = "{literal}" }} }}\n'
    )
    assessment = migration.assess_migration_state(_build_modelo(tmp_path, successor_extra=declaration))
    matches = [
        item
        for item in assessment.unresolved_duplication
        if item.get("member") == "modelo-999-cuota" and item.get("fields") == ["expression.literal"]
    ]

    assert bool(matches) is redundant
    formula_row = next(
        row for row in assessment.by_revision_family if row["revision"] == "2025" and row["family"] == "formulas"
    )
    measured = formula_row["redundant_overrides"] if redundant else formula_row["genuine_overrides"]
    assert _positive(measured)


def test_removal_clearing_ordering_and_source_defaults_are_separate_operations(tmp_path: Path) -> None:
    declaration = (
        'formula_source_refs = ["successor-source"]\n'
        'cleared_families = ["constructs"]\n'
        '[[revisions."2025".family_removals]]\n'
        'family = "formulas"\n'
        'selector = { revision = "2024", id = "modelo-999-cuota" }\n'
        '[[revisions."2025".family_positions]]\n'
        'family = "formulas"\n'
        'id = "modelo-999-recargo"\n'
        "position = 0\n"
    )
    modelo = _build_modelo(tmp_path, successor_extra=declaration)
    successor_constructs = modelo / "revisions" / "2025" / "constructs"
    for path in successor_constructs.glob("*.toml"):
        path.unlink()
    successor_constructs.rmdir()

    assessment = migration.assess_migration_state(modelo)

    formulas = next(
        row for row in assessment.by_revision_family if row["revision"] == "2025" and row["family"] == "formulas"
    )
    constructs = next(
        row for row in assessment.by_revision_family if row["revision"] == "2025" and row["family"] == "constructs"
    )
    scalars = next(
        row for row in assessment.by_revision_family if row["revision"] == "2025" and row["family"] == "$scalars"
    )
    assert formulas["removals"] == 1
    assert _positive(formulas["structural_overhead"])
    assert constructs["removals"] == 1
    assert _positive(scalars["authored_payload_fields"])


def test_evidence_difference_is_genuine_while_surrounding_restatement_remains_visible(tmp_path: Path) -> None:
    modelo = _build_modelo(tmp_path)
    formulas = modelo / "revisions" / "2025" / "formulas" / "0001-formulas.toml"
    formulas.write_text(
        formulas.read_text(encoding="utf-8").replace(
            'source_refs = ["aeat-manual"]', 'source_refs = ["changed-evidence"]', 1
        ),
        encoding="utf-8",
        newline="\n",
    )

    assessment = migration.assess_migration_state(modelo)
    recargo = next(
        item
        for item in assessment.unresolved_duplication
        if item.get("revision") == "2025"
        and item.get("family") == "formulas"
        and item.get("member") == "modelo-999-recargo"
    )

    assert "source_refs" not in _fields(recargo)
    assert "expression.literal" in _fields(recargo)
    row = next(
        item for item in assessment.by_revision_family if item["revision"] == "2025" and item["family"] == "formulas"
    )
    assert _positive(row["genuine_overrides"])


def test_unsupported_collection_shape_reports_incomplete_coverage_before_hydration(tmp_path: Path) -> None:
    modelo = _build_modelo(tmp_path)
    formulas = modelo / "revisions" / "2025" / "formulas" / "0001-formulas.toml"
    formulas.write_text(
        '[revisions."2025".formulas]\nid = "unsupported-mapping-shape"\n',
        encoding="utf-8",
        newline="\n",
    )

    assessment = migration.assess_migration_state(modelo)

    assert not assessment.minimal
    assert assessment.by_revision_family == ()
    assert any(
        item["revision"] == "2025" and item["family"] == "formulas" and item["reason"] == "authored_shape_unsupported"
        for item in assessment.blocked_work
    )
