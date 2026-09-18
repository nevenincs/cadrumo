"""Detector teeth for registry-wide collapse verification."""

from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.domain.calculations.registry.casilla_lineage import CasillaLineageOrigin
from cadrumo.domain.calculations.registry.lineage_attestation import LineageAttestation
from cadrumo.domain.calculations.registry.schema import SupportedFilingYearsCatalogue
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition
from dev.registry.edition_delta_migration import MigrationAssessment, assess_migration_state
from dev.registry.tests.test_restated_family_merge import _build_modelo

from .. import registry_collapse_verification as verification

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _support() -> SupportedFilingYearsCatalogue:
    return SupportedFilingYearsCatalogue(floor=2024, horizon=2025, hard_ceiling=2025)


def _finding_fields(item: object) -> tuple[object, ...]:
    if not isinstance(item, dict):
        return ()
    fields = item.get("fields")
    return tuple(fields) if isinstance(fields, list | tuple) else ()


def test_finding_transition_detects_replacement_when_counts_are_equal(tmp_path: Path) -> None:
    assessment = assess_migration_state(_build_modelo(tmp_path))
    original = assessment.unresolved_duplication[0]
    replacement = {**original, "member": "new-defect-at-same-count"}
    changed = replace(assessment, unresolved_duplication=(replacement, *assessment.unresolved_duplication[1:]))

    transition = verification.finding_transition(assessment, changed)

    assert len(transition["removed"]) == 1
    assert len(transition["added"]) == 1
    assert transition["unchanged"] == len(assessment.unresolved_duplication) - 1


def test_assessor_scope_reconciliation_detects_a_skipped_family(monkeypatch: pytest.MonkeyPatch) -> None:
    retained = tuple(spec for spec in verification.CANONICAL_FAMILY_SPECS if spec.section != "formulas")
    monkeypatch.setattr(verification, "CANONICAL_FAMILY_SPECS", retained)

    assert verification.assessor_scope_gaps() == (
        {"revision": "*", "family": "formulas", "reason": "assessor_family_not_enrolled"},
    )


def test_assessor_scope_reconciliation_detects_a_skipped_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    retained = tuple(spec for spec in verification.CANONICAL_FAMILY_SPECS if not spec.singleton)
    monkeypatch.setattr(verification, "CANONICAL_FAMILY_SPECS", retained)

    assert verification.assessor_scope_gaps() == (
        {"revision": "*", "family": "completeness_manifest", "reason": "assessor_family_not_enrolled"},
    )


def test_assessment_coverage_detects_a_skipped_scalar_bucket(tmp_path: Path) -> None:
    source = _build_modelo(tmp_path)
    modelo = verification.load_modelo_directory(source)
    assessment = assess_migration_state(source)
    rows = tuple(row for row in assessment.by_revision_family if row.get("family") != "$scalars")

    gaps = verification.assessment_coverage_gaps(
        replace(assessment, by_revision_family=rows),
        modelo,
        stage="source",
    )

    assert {str(item["revision"]) for item in gaps} == {"2024", "2025"}
    assert {item["family"] for item in gaps} == {"$scalars"}
    assert {item["reason"] for item in gaps} == {"assessment_row_missing"}


def test_explicit_root_is_classified_instead_of_becoming_a_minimality_blind_spot(tmp_path: Path) -> None:
    modelo = _build_modelo(tmp_path)
    manifest = modelo / "revisions" / "2025" / "revision.toml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            'predecessor = "2024"',
            'predecessor = { none = { cause = "predecessor_row_without_lineage", reason = "migration" } }',
        ),
        encoding="utf-8",
        newline="\n",
    )

    roots = verification.root_eligibility(modelo)

    successor = [item for item in roots if item["revision"] == "2025" and item["family"] == "formulas"]
    assert successor == [
        {
            "revision": "2025",
            "family": "formulas",
            "status": verification.RootEligibility.CANDIDATE,
            "candidate": "2024",
            "explicit_root": True,
        }
    ]
    overlap = verification.root_overlap_diagnostics(modelo, roots)
    assert any(
        item["revision"] == "2025"
        and item["family"] == "formulas"
        and item["reason"] == "raw same-storage-id overlap requires baseline conversion proof"
        for item in overlap
    )


def test_parallel_applicability_branch_is_not_reported_as_a_storage_candidate(tmp_path: Path) -> None:
    modelo = _build_modelo(tmp_path)
    manifest = modelo / "revisions" / "2025" / "revision.toml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8")
        .replace("valid_from = 2025-01-01", "valid_from = 2024-01-01")
        .replace(
            'period_selector = { years = [2025], periods = ["0A"] }',
            'period_selector = { years = [2024], periods = ["0A"] }',
        )
        .replace('predecessor = "2024"', 'predecessor = { none = { reason = "parallel scheme" } }'),
        encoding="utf-8",
        newline="\n",
    )

    roots = verification.root_eligibility(modelo)

    successor = [item for item in roots if item["revision"] == "2025" and item["family"] == "formulas"]
    assert successor[0]["status"] == verification.RootEligibility.INCOMPATIBLE


def test_grounded_lower_grade_root_is_not_reported_as_a_storage_candidate(tmp_path: Path) -> None:
    modelo = _build_modelo(tmp_path)
    manifest = modelo / "revisions" / "2025" / "revision.toml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            'predecessor = "2024"',
            'predecessor = { none = { cause = "lower_grade", reason = "The successor has lower authority." } }',
        ),
        encoding="utf-8",
        newline="\n",
    )

    successor = [
        item
        for item in verification.root_eligibility(modelo)
        if item["revision"] == "2025" and item["family"] == "casillas"
    ]

    assert successor[0]["status"] == verification.RootEligibility.INCOMPATIBLE


def test_nonminimal_unchanged_candidate_is_reported_as_a_converter_defect(tmp_path: Path) -> None:
    source = _build_modelo(tmp_path / "source")
    candidate = tmp_path / "candidate"

    def dishonest_noop(_source: Path, _candidate: Path) -> dict[str, object]:
        return {"complete": True}

    result = verification._verify_one(
        "999",
        source,
        candidate,
        support=_support(),
        floor=2024,
        ceiling=2025,
        converter=dishonest_noop,
    )

    assert result["outcome"] == verification.ModeloOutcome.PARTIAL
    assert result["converter_defect"] == "converter_claimed_completion_without_changing_nonminimal_input"
    assert result["source_apply_readiness"] == verification.CheckStatus.FAILED


def test_canonical_converter_carries_cross_model_dependency_closure_into_idempotence(tmp_path: Path) -> None:
    source = verification.REPO_ROOT / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "modelos" / "390"
    candidate = tmp_path / "candidates" / "390" / "registry" / "aeat" / "modelos" / "390"
    candidate.parent.mkdir(parents=True)
    shutil.copytree(source, candidate)

    verification.canonical_converter(source, candidate)
    first = verification.fingerprint_digest(verification.fingerprint_tree(candidate))
    assert (candidate.parent / "303").is_dir()

    verification.canonical_converter(candidate, candidate)

    assert verification.fingerprint_digest(verification.fingerprint_tree(candidate)) == first


def test_typed_comparison_preserves_absence_false_zero_empty_and_order(tmp_path: Path) -> None:
    source = _build_modelo(tmp_path / "source")
    before = verification.load_modelo_directory(source)
    candidate = tmp_path / "candidate"
    shutil.copytree(source, candidate)
    formula = candidate / "revisions" / "2025" / "formulas" / "0001-formulas.toml"
    formula.write_text(
        formula.read_text(encoding="utf-8").replace('literal = "0"', 'literal = "7"', 1),
        encoding="utf-8",
        newline="\n",
    )
    after = verification.load_modelo_directory(candidate)

    result = verification.compare_modelos(before, after)

    assert result.status is verification.CheckStatus.FAILED
    assert result.differences[0]["reason"] == "value_changed"


def test_typed_comparison_normalizes_valid_lineage_sidecar_without_hiding_provenance(tmp_path: Path) -> None:
    loaded = verification.load_modelo_directory(_build_modelo(tmp_path))
    revision = loaded.revisions["2025"]
    casillas = tuple(
        casilla.model_copy(update={"continuidad_origin": CasillaLineageOrigin.SEEDED, "continuidad_evidence": None})
        if str(casilla.continuidad_id) == "cuota"
        else casilla
        for casilla in revision.casillas
    )
    row = next(casilla for casilla in casillas if str(casilla.continuidad_id) == "cuota")
    attestation = LineageAttestation(
        family="casillas",
        continuidad_id="cuota",
        from_revision="2024",
        to_revision="2025",
        origin="seeded",
        legal_refs=row.legal_refs,
        source_refs=row.source_refs,
    )
    inline_revision = revision.model_copy(update={"casillas": casillas})
    sidecar_revision = inline_revision.model_copy(update={"lineage_attestations": (attestation,)})
    inline = loaded.model_copy(update={"revisions": {**loaded.revisions, "2025": inline_revision}})
    sidecar = loaded.model_copy(update={"revisions": {**loaded.revisions, "2025": sidecar_revision}})

    assert verification.compare_modelos(inline, sidecar).status is verification.CheckStatus.PASSED

    altered = attestation.model_copy(update={"source_refs": ("other-source",)})
    altered_revision = inline_revision.model_copy(update={"lineage_attestations": (altered,)})
    altered_modelo = loaded.model_copy(update={"revisions": {**loaded.revisions, "2025": altered_revision}})
    result = verification.compare_modelos(inline, altered_modelo)
    assert result.status is verification.CheckStatus.FAILED
    assert result.differences[0]["reason"] == "lineage_attestation_provenance_differs_from_hydrated_casilla"


def test_successor_default_drift_makes_matching_predecessor_source_override_genuine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    finding = {
        "revision": "2025",
        "family": "casillas",
        "member": "0001",
        "fields": ["source_refs"],
        "reason": "authored override equals hydrated baseline",
    }
    assessment = MigrationAssessment(
        fingerprint="sha256:test",
        input_fingerprints=(),
        inputs_stable=True,
        physical_bytes=1,
        authored_payload_fields=1,
        inherited_payload_fields=0,
        genuine_overrides=0,
        redundant_overrides=1,
        additions=0,
        removals=0,
        structural_overhead=0,
        unresolved_duplication=(finding,),
        blocked_work=(),
        by_revision_family=(
            {"revision": "2025", "family": "casillas", "genuine_overrides": 0, "redundant_overrides": 1},
        ),
    )
    monkeypatch.setattr(
        verification,
        "load_modelo_declarations",
        lambda _path: {
            "revisions": {
                "2025": {
                    "casilla_source_refs": ["successor-default"],
                    "casilla_overrides": [
                        {"selector": {"id": "0001"}, "fields": {"source_refs": ["predecessor-source"]}}
                    ],
                }
            }
        },
    )

    normalized = verification.normalized_assessment(tmp_path, assessment)

    assert normalized.minimal
    assert normalized.genuine_overrides == 1
    assert normalized.redundant_overrides == 0
    assert normalized.by_revision_family[0]["genuine_overrides"] == 1
    assert normalized.by_revision_family[0]["redundant_overrides"] == 0


def test_override_equal_to_successor_default_remains_redundant(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    finding = {
        "revision": "2025",
        "family": "casillas",
        "member": "0001",
        "fields": ["source_refs"],
        "reason": "authored override equals hydrated baseline",
    }
    assessment = MigrationAssessment(
        fingerprint="sha256:test",
        input_fingerprints=(),
        inputs_stable=True,
        physical_bytes=1,
        authored_payload_fields=1,
        inherited_payload_fields=0,
        genuine_overrides=0,
        redundant_overrides=1,
        additions=0,
        removals=0,
        structural_overhead=0,
        unresolved_duplication=(finding,),
        blocked_work=(),
        by_revision_family=(),
    )
    monkeypatch.setattr(
        verification,
        "load_modelo_declarations",
        lambda _path: {
            "revisions": {
                "2025": {
                    "casilla_source_refs": ["same-source"],
                    "casilla_overrides": [{"selector": {"id": "0001"}, "fields": {"source_refs": ["same-source"]}}],
                }
            }
        },
    )

    assert verification.normalized_assessment(tmp_path, assessment) is assessment


def test_reused_storage_id_with_new_lineage_is_an_addition_not_a_redundant_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    finding = {
        "revision": "2025",
        "family": "casillas",
        "member": "01",
        "fields": ["data_type", "number"],
        "reason": "authored value equals hydrated baseline",
    }
    assessment = MigrationAssessment(
        fingerprint="sha256:test",
        input_fingerprints=(),
        inputs_stable=True,
        physical_bytes=1,
        authored_payload_fields=2,
        inherited_payload_fields=0,
        genuine_overrides=0,
        redundant_overrides=2,
        additions=0,
        removals=0,
        structural_overhead=0,
        unresolved_duplication=(finding,),
        blocked_work=(),
        by_revision_family=(
            {
                "revision": "2025",
                "family": "casillas",
                "genuine_overrides": 0,
                "redundant_overrides": 2,
                "additions": 0,
            },
        ),
    )
    monkeypatch.setattr(
        verification,
        "load_modelo_declarations",
        lambda _path: {
            "revisions": {
                "2024": {"casillas": [{"id": "01", "continuidad_id": "old-concept"}]},
                "2025": {
                    "predecessor": "2024",
                    "casillas": [{"id": "01", "continuidad_id": "new-concept", "number": "01"}],
                },
            }
        },
    )

    normalized = verification.normalized_assessment(tmp_path, assessment)

    assert normalized.minimal
    assert normalized.redundant_overrides == 0
    assert normalized.genuine_overrides == 0
    assert normalized.additions == 1
    assert normalized.by_revision_family[0]["redundant_overrides"] == 0
    assert normalized.by_revision_family[0]["additions"] == 1


@pytest.mark.parametrize("required_field", ["number", "section"])
def test_new_storage_row_still_requires_schema_fields(tmp_path: Path, required_field: str) -> None:
    modelo = verification.load_modelo_directory(_build_modelo(tmp_path))
    payload = modelo.revisions["2025"].casillas[0].model_dump(mode="python")
    payload.pop(required_field)

    with pytest.raises(ValidationError, match=required_field):
        CasillaDefinition.model_validate(payload)


def test_tree_fingerprint_detects_changed_input(tmp_path: Path) -> None:
    source = _build_modelo(tmp_path)
    before = verification.fingerprint_tree(source)
    manifest = source / "manifest.toml"
    manifest.write_text(manifest.read_text(encoding="utf-8") + "\n", encoding="utf-8", newline="\n")

    after = verification.fingerprint_tree(source)

    assert before != after
    assert verification.fingerprint_digest(before) != verification.fingerprint_digest(after)


def test_request_matrix_includes_authored_and_global_boundary_coordinates(tmp_path: Path) -> None:
    modelo = verification.load_modelo_directory(_build_modelo(tmp_path))

    matrix = verification.request_matrix(modelo, floor=2023, ceiling=2026)

    cases = {item.case for item in matrix}
    assert {"exact", "valid_from", "valid_to", "support_floor", "support_ceiling"} <= cases


def test_assessment_fixture_contains_complete_member_and_nested_override_findings(tmp_path: Path) -> None:
    assessment: MigrationAssessment = assess_migration_state(_build_modelo(tmp_path))

    formula_findings = [item for item in assessment.unresolved_duplication if item.get("family") == "formulas"]
    assert any(len(_finding_fields(item)) > 1 for item in formula_findings)
    assert any("expression.literal" in _finding_fields(item) for item in formula_findings)
