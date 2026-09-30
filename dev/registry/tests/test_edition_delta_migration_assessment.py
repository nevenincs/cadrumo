"""Focused regression tests for migration measurement and report coverage."""

from __future__ import annotations

from pathlib import Path

import pytest

import dev.registry.edition_delta_migration as migration
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from dev._paths import REPO_ROOT
from dev.registry.conformance.loader_directory_mode_support import write_standard_manifest
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


def test_typed_comparison_matches_an_authored_token_to_its_typed_enum() -> None:
    """Authored TOML states the token; the typed model holds the enum. Both are one fact."""
    assert migration._typed_equal("computed", InputKind.COMPUTED)
    assert migration._typed_equal(InputKind.BOUND, "bound")
    assert not migration._typed_equal("bound", InputKind.COMPUTED)


def test_only_converter_failure_roots_are_reassessed_against_the_adjacent_revision() -> None:
    """The structured cause decides, and a root naming a legal or topology cause stays a root."""
    technical = {"predecessor": {"none": {"cause": "predecessor_row_without_lineage", "reason": "..."}}}
    structural = {"predecessor": {"none": {"cause": "official_structure_differs", "reason": "..."}}}

    assert migration.technical_root(technical)
    assert not migration.technical_root(structural)


def test_a_roots_prose_never_decides_whether_it_is_reconsidered() -> None:
    """Free text is not a second spelling of the cause, however closely it reads like one.

    Both declarations below describe a converter limitation in words, one of
    them quoting a cause token verbatim. Neither states the typed field, so
    neither is classified: the reassessment acts on the declaration's own
    claim, not on how its author happened to phrase the sentence beside it.
    """
    quoting_a_cause = {"predecessor": {"none": {"reason": "migration hit predecessor_row_without_lineage here"}}}
    describing_one = {"predecessor": {"none": {"reason": "the earlier rows carry no lineage to chain to"}}}

    assert not migration.technical_root(quoting_a_cause)
    assert not migration.technical_root(describing_one)


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
    assert _positive(completeness[0]["authored_payload_fields"])
    assert all(_positive(row["genuine_overrides"]) for row in completeness[1:])
    assert all(_positive(row["authored_payload_fields"]) for row in scalars)
    assert assessment.inputs_stable
    assert assessment.input_fingerprints == before == migration._file_fingerprints(_MODELO_100)
    assert assessment.redundant_overrides == 0
    assert assessment.minimal


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
        'cleared_families = [{ family = "constructs", cause = "official_structure_withdraws", '
        'reason = "The document governing this edition lays out no construct, so the earlier one is withdrawn." }]\n'
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


def test_a_predecessor_row_an_authored_operation_claims_is_not_free_to_rename() -> None:
    """An authored override patches its row and an authored removal relocates it; neither is free."""
    manifest = {
        "casilla_overrides": [{"selector": {"revision": "2021", "id": "0800"}, "fields": {"section": ["x"]}}],
        "casilla_removals": [{"selector": {"revision": "2021", "id": "0786"}}],
    }

    assert migration._authored_override_selectors(manifest) == frozenset({"0800", "0786"})
    assert migration._authored_override_selectors({}) == frozenset()


def test_a_row_override_states_exactly_one_source_reference_form() -> None:
    """Additions over a stored whole list remove it; a whole list displaces stored additions."""
    stored_whole = {"id": "0001", "source_refs": ["a"]}
    stored_additions = {"id": "0001", "additional_source_refs": ["b"]}

    assert migration._reconcile_source_removals({"additional_source_refs": ["c"]}, (), stored_whole) == ("source_refs",)
    assert (
        migration._reconcile_source_removals({"source_refs": ["c"]}, ("additional_source_refs",), stored_additions)
        == ()
    )
    assert migration._reconcile_source_removals({"additional_source_refs": ["c"]}, (), stored_additions) == ()


def test_a_constraints_override_states_exactly_one_source_reference_form() -> None:
    """The constraints table is patched as a plain table, so each displaced spelling is removed explicitly."""
    stored_whole = {"id": "0001", "constraints": {"max_value": "9", "source_refs": ["a", "b"]}}
    stored_additions = {"id": "0001", "constraints": {"max_value": "9", "additional_source_refs": ["b"]}}

    assert migration._reconcile_source_removals(
        {"constraints": {"additional_source_refs": ["c"]}}, (), stored_whole
    ) == ("constraints.source_refs",)
    assert migration._reconcile_source_removals({"constraints": {"source_refs": ["c"]}}, (), stored_additions) == (
        "constraints.additional_source_refs",
    )
    assert migration._reconcile_source_removals({"constraints": {"source_refs": ["c"]}}, (), stored_whole) == ()
    assert migration._reconcile_source_removals(
        {"constraints": {"source_refs": ["c"]}}, ("constraints.additional_source_refs",), stored_additions
    ) == ("constraints.additional_source_refs",)


_ROOT_REF = "ley-58-2003:art-29"


def _root_fixture(
    root: Path,
    *,
    successor_root: str,
    successor_number: str = "1",
    successor_formula: str = "modelo-999-2025-cuota",
    successor_window: tuple[str, str] = ("2025-01-01", "2025-12-31"),
) -> Path:
    """A 2024 edition and a 2025 edition declaring ``successor_root`` as its predecessor.

    Each edition names its own formula through its own edition key, as the
    corpus does, so a row referencing it restates the earlier row only once the
    edition tokens are set aside.
    """
    modelo_dir = root / "999"
    modelo_dir.mkdir(parents=True)
    write_standard_manifest(modelo_dir, "Root fixture")
    for revision_id, year, predecessor, number, formula, (valid_from, valid_to) in (
        ("2024", 2024, "", "1", "modelo-999-2024-cuota", ("2024-01-01", "2024-12-31")),
        ("2025", 2025, successor_root, successor_number, successor_formula, successor_window),
    ):
        revision_dir = modelo_dir / "revisions" / revision_id
        for section in ("casillas", "formulas"):
            (revision_dir / section).mkdir(parents=True)
        (revision_dir / "revision.toml").write_text(
            f'[revisions."{revision_id}"]\nvalid_from = {valid_from}\nvalid_to = {valid_to}\n'
            f'period_selector = {{ years = [{year}], periods = ["0A"] }}\n'
            f'legal_refs = ["{_ROOT_REF}"]\nsource_refs = ["aeat-manual"]\n{predecessor}',
            encoding="utf-8",
            newline="\n",
        )
        (revision_dir / "casillas" / "0001-casillas.toml").write_text(
            f'[[revisions."{revision_id}".casillas]]\nid = "0001"\nnumber = "{number}"\n'
            f'section = ["liquidacion"]\ndata_type = "money"\ninput_kind = "computed"\nformula = "{formula}"\n'
            f'legal_refs = ["{_ROOT_REF}"]\nsource_refs = ["aeat-manual"]\n',
            encoding="utf-8",
            newline="\n",
        )
        (revision_dir / "formulas" / "0001-formulas.toml").write_text(
            f'[[revisions."{revision_id}".formulas]]\nid = "{formula}"\ntarget_casilla_id = "0001"\n'
            f'expression = {{ literal = "0" }}\nlegal_refs = ["{_ROOT_REF}"]\nsource_refs = ["aeat-manual"]\n',
            encoding="utf-8",
            newline="\n",
        )
    return modelo_dir


_UNCAUSED_ROOT = (
    'predecessor = { none = { reason = "Stated in full.", '
    f'legal_refs = ["{_ROOT_REF}"], source_refs = ["aeat-manual"] }} }}\n'
)
_CAUSED_ROOT = (
    'predecessor = { none = { cause = "official_structure_differs", reason = "The design differs.", '
    f'legal_refs = ["{_ROOT_REF}"], source_refs = ["aeat-manual"] }} }}\n'
)


def _root_restatement(assessment: migration.MigrationAssessment) -> list[str]:
    return [
        field
        for item in assessment.unresolved_duplication
        if item.get("revision") == "2025"
        and item.get("family") == "casillas"
        and str(item.get("reason", "")).startswith("explicit root restates")
        for field in _fields(item)
    ]


@pytest.mark.parametrize("declaration", [_UNCAUSED_ROOT, _CAUSED_ROOT], ids=["uncaused", "caused"])
def test_an_explicit_root_restating_the_edition_before_it_is_not_minimal(tmp_path: Path, declaration: str) -> None:
    """A root declaration decides legal continuity, not whether the payload it states is stored already.

    The row differs from the one before it only by the edition key inside its
    formula reference, which inheritance resolves to the inheriting edition's
    own declaration, so every field it states is restatement. A root was never
    measured, and reported minimal however much it restated.
    """
    assessment = migration.assess_migration_state(_root_fixture(tmp_path, successor_root=declaration))

    restated = _root_restatement(assessment)
    assert {"data_type", "formula", "input_kind", "number", "section"} <= set(restated)
    assert not assessment.minimal


def test_a_reference_to_another_lineage_is_a_genuine_difference_net_of_edition_tokens(tmp_path: Path) -> None:
    """Detector teeth for the normalisation: only the edition's own key is set aside."""
    modelo_dir = _root_fixture(
        tmp_path, successor_root=_UNCAUSED_ROOT, successor_number="7", successor_formula="modelo-999-2025-recargo"
    )

    restated = _root_restatement(migration.assess_migration_state(modelo_dir))

    assert "formula" not in restated
    assert "number" not in restated
    assert "section" in restated


def test_a_root_whose_every_statement_differs_stays_minimal(tmp_path: Path) -> None:
    """The normal path: a root with nothing to reuse from the edition before it reports clean."""
    modelo_dir = _root_fixture(tmp_path, successor_root=_UNCAUSED_ROOT)
    casillas = modelo_dir / "revisions" / "2025" / "casillas" / "0001-casillas.toml"
    casillas.write_text(
        '[[revisions."2025".casillas]]\nid = "0009"\nnumber = "9"\nsection = ["resultado"]\n'
        'data_type = "money"\ninput_kind = "computed"\nformula = "modelo-999-2025-cuota"\n'
        f'legal_refs = ["{_ROOT_REF}"]\nsource_refs = ["aeat-manual"]\n',
        encoding="utf-8",
        newline="\n",
    )
    formulas = modelo_dir / "revisions" / "2025" / "formulas" / "0001-formulas.toml"
    formulas.write_text(
        formulas.read_text(encoding="utf-8").replace('target_casilla_id = "0001"', 'target_casilla_id = "0009"'),
        encoding="utf-8",
        newline="\n",
    )

    assessment = migration.assess_migration_state(modelo_dir)

    assert _root_restatement(assessment) == []
    assert assessment.minimal


def test_a_parallel_root_in_force_beside_the_edition_before_it_is_not_measured_against_it(tmp_path: Path) -> None:
    """A variant whose validity window meets its neighbour's is not the edition after it."""
    modelo_dir = _root_fixture(tmp_path, successor_root=_UNCAUSED_ROOT, successor_window=("2024-01-01", "2025-12-31"))

    assert _root_restatement(migration.assess_migration_state(modelo_dir)) == []
