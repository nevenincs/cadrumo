"""Detector teeth for registry-wide collapse verification."""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from dataclasses import replace
from functools import partial
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.casilla_lineage import CasillaLineageOrigin
from cadrumo.domain.calculations.registry.facts.payloads import EntitySetFactPayload
from cadrumo.domain.calculations.registry.lineage_attestation import LineageAttestation
from cadrumo.domain.calculations.registry.schema import SupportedFilingYearsCatalogue
from cadrumo.domain.calculations.registry.schema_form_layouts import FormLayoutDefinition, FormPlacementDefinition
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition
from dev._paths import REPO_ROOT
from dev.packaging import authority_staging
from dev.registry.compiler.loader import load_modelo_directory
from dev.registry.edition_delta_assessment import MigrationAssessment, assess_migration_state
from dev.registry.tests.test_restated_family_merge import _build_modelo

from .. import registry_collapse_assessment as _collapse_assessment
from .. import registry_collapse_assessment_normalization as _collapse_assessment_normalization
from .. import registry_collapse_authority_queries as _collapse_authority_queries
from .. import registry_collapse_candidate as _collapse_candidate
from .. import registry_collapse_comparison as _collapse_comparison
from .. import registry_collapse_converter as _collapse_converter
from .. import registry_collapse_fingerprints as _collapse_fingerprints
from .. import registry_collapse_models as _collapse_models
from .. import registry_collapse_requests as _collapse_requests
from .. import registry_collapse_roots as _collapse_roots
from .. import registry_collapse_run as _collapse_run

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

    transition = _collapse_assessment.finding_transition(assessment, changed)

    assert len(transition["removed"]) == 1
    assert len(transition["added"]) == 1
    assert transition["unchanged"] == len(assessment.unresolved_duplication) - 1


def test_assessor_scope_reconciliation_detects_a_skipped_family(monkeypatch: pytest.MonkeyPatch) -> None:
    retained = tuple(spec for spec in _collapse_assessment.CANONICAL_FAMILY_SPECS if spec.section != "formulas")
    monkeypatch.setattr(_collapse_assessment, "CANONICAL_FAMILY_SPECS", retained)

    assert _collapse_assessment.assessor_scope_gaps() == (
        {"revision": "*", "family": "formulas", "reason": "assessor_family_not_enrolled"},
    )


def test_assessor_scope_reconciliation_detects_a_skipped_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    retained = tuple(spec for spec in _collapse_assessment.CANONICAL_FAMILY_SPECS if not spec.singleton)
    monkeypatch.setattr(_collapse_assessment, "CANONICAL_FAMILY_SPECS", retained)

    assert _collapse_assessment.assessor_scope_gaps() == (
        {"revision": "*", "family": "completeness_manifest", "reason": "assessor_family_not_enrolled"},
    )


def test_assessment_coverage_detects_a_skipped_scalar_bucket(tmp_path: Path) -> None:
    source = _build_modelo(tmp_path)
    modelo = load_modelo_directory(source)
    assessment = assess_migration_state(source)
    rows = tuple(row for row in assessment.by_revision_family if row.get("family") != "$scalars")

    gaps = _collapse_assessment.assessment_coverage_gaps(
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

    roots = _collapse_roots.root_eligibility(modelo)

    successor = [item for item in roots if item["revision"] == "2025" and item["family"] == "formulas"]
    assert successor == [
        {
            "revision": "2025",
            "family": "formulas",
            "status": _collapse_models.RootEligibility.CANDIDATE,
            "candidate": "2024",
            "explicit_root": True,
        }
    ]
    overlap = _collapse_roots.root_overlap_diagnostics(modelo, roots)
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

    roots = _collapse_roots.root_eligibility(modelo)

    successor = [item for item in roots if item["revision"] == "2025" and item["family"] == "formulas"]
    assert successor[0]["status"] == _collapse_models.RootEligibility.INCOMPATIBLE


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
        for item in _collapse_roots.root_eligibility(modelo)
        if item["revision"] == "2025" and item["family"] == "casillas"
    ]

    assert successor[0]["status"] == _collapse_models.RootEligibility.INCOMPATIBLE


def test_nonminimal_unchanged_candidate_is_reported_as_a_converter_defect(tmp_path: Path) -> None:
    source = _build_modelo(tmp_path / "source")
    candidate = tmp_path / "candidate"

    def dishonest_noop(_source: Path, _candidate: Path) -> dict[str, object]:
        return {"complete": True}

    result = _collapse_candidate._verify_one(
        "999",
        source,
        candidate,
        support=_support(),
        floor=2024,
        ceiling=2025,
        converter=dishonest_noop,
    )

    assert result["outcome"] == _collapse_models.ModeloOutcome.PARTIAL
    assert result["converter_defect"] == "converter_claimed_completion_without_changing_nonminimal_input"
    assert result["source_apply_readiness"] == _collapse_models.CheckStatus.FAILED


def test_canonical_converter_carries_cross_model_dependency_closure_into_idempotence(tmp_path: Path) -> None:
    source = REPO_ROOT / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "modelos" / "390"
    candidate = tmp_path / "candidates" / "390" / "registry" / "aeat" / "modelos" / "390"
    candidate.parent.mkdir(parents=True)
    shutil.copytree(source, candidate)

    _collapse_converter.canonical_converter(source, candidate)
    first = _collapse_fingerprints.fingerprint_digest(_collapse_fingerprints.fingerprint_tree(candidate))
    assert (candidate.parent / "303").is_dir()

    _collapse_converter.canonical_converter(candidate, candidate)

    assert _collapse_fingerprints.fingerprint_digest(_collapse_fingerprints.fingerprint_tree(candidate)) == first


def test_typed_comparison_preserves_absence_false_zero_empty_and_order(tmp_path: Path) -> None:
    source = _build_modelo(tmp_path / "source")
    before = load_modelo_directory(source)
    candidate = tmp_path / "candidate"
    shutil.copytree(source, candidate)
    formula = candidate / "revisions" / "2025" / "formulas" / "0001-formulas.toml"
    formula.write_text(
        formula.read_text(encoding="utf-8").replace('literal = "0"', 'literal = "7"', 1),
        encoding="utf-8",
        newline="\n",
    )
    after = load_modelo_directory(candidate)

    result = _collapse_comparison.compare_modelos(before, after)

    assert result.status is _collapse_models.CheckStatus.FAILED
    assert result.differences[0]["reason"] == "value_changed"


def test_typed_comparison_reads_an_entity_set_as_a_set() -> None:
    """Equal entity sets compare equal however their members were inserted; a changed member still differs."""
    members = ("subvencion_corriente", "subvencion_capital", "indemnizacion")
    forward = EntitySetFactPayload(entities=frozenset(members))
    backward = EntitySetFactPayload(entities=frozenset(reversed(members)))
    changed = EntitySetFactPayload(entities=frozenset((*members[:2], "subvencion_explotacion")))

    projected = _collapse_comparison._typed_projection(forward)

    assert isinstance(projected, Mapping)
    assert projected["entities"] == sorted(members)
    assert _collapse_comparison._first_difference(projected, _collapse_comparison._typed_projection(backward)) is None
    assert (
        _collapse_comparison._first_difference(projected, _collapse_comparison._typed_projection(changed)) is not None
    )


def test_typed_comparison_normalizes_valid_lineage_sidecar_without_hiding_provenance(tmp_path: Path) -> None:
    loaded = load_modelo_directory(_build_modelo(tmp_path))
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

    assert _collapse_comparison.compare_modelos(inline, sidecar).status is _collapse_models.CheckStatus.PASSED

    altered = attestation.model_copy(update={"source_refs": ("other-source",)})
    altered_revision = inline_revision.model_copy(update={"lineage_attestations": (altered,)})
    altered_modelo = loaded.model_copy(update={"revisions": {**loaded.revisions, "2025": altered_revision}})
    result = _collapse_comparison.compare_modelos(inline, altered_modelo)
    assert result.status is _collapse_models.CheckStatus.FAILED
    assert result.differences[0]["reason"] == "mapping_keys_changed"
    assert (
        _collapse_comparison.compare_modelos(altered_modelo, altered_modelo).status
        is _collapse_models.CheckStatus.PASSED
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_refs", ("other-source",)),
        ("legal_refs", ("other:article",)),
        ("from_revision", "2021"),
        ("to_revision", "2024"),
    ],
)
def test_distinct_lineage_citations_and_edges_survive_typed_comparison(field: str, value: object) -> None:
    modelo = load_modelo_directory(REPO_ROOT / "src/cadrumo/_data/registry/aeat/modelos/188")
    revision = modelo.revisions["2023-y-siguientes"]
    assert revision.lineage_attestations
    assert _collapse_comparison.compare_modelos(modelo, modelo).status is _collapse_models.CheckStatus.PASSED
    rows = {c.continuidad_id: c for c in revision.casillas}
    index = next(
        index
        for index, attestation in enumerate(revision.lineage_attestations)
        if attestation.source_refs != rows[attestation.continuidad_id].source_refs
    )
    changed = revision.lineage_attestations[index].model_copy(update={field: value})
    attestations = (*revision.lineage_attestations[:index], changed, *revision.lineage_attestations[index + 1 :])
    changed_revision = revision.model_copy(update={"lineage_attestations": attestations})
    after = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: changed_revision}})
    result = _collapse_comparison.compare_modelos(modelo, after)
    assert result.status is _collapse_models.CheckStatus.FAILED
    assert "lineage_attestations" in str(result.differences[0]["location"])
    removed_revision = revision.model_copy(update={"lineage_attestations": ()})
    removed = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: removed_revision}})
    assert _collapse_comparison.compare_modelos(modelo, removed).status is _collapse_models.CheckStatus.FAILED


def test_lineage_claim_projection_still_refuses_an_unhydrated_origin() -> None:
    modelo = load_modelo_directory(REPO_ROOT / "src/cadrumo/_data/registry/aeat/modelos/188")
    revision = modelo.revisions["2023-y-siguientes"]
    changed = revision.lineage_attestations[0].model_copy(update={"origin": CasillaLineageOrigin.SEEDED})
    changed_revision = revision.model_copy(
        update={"lineage_attestations": (changed, *revision.lineage_attestations[1:])}
    )
    after = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: changed_revision}})
    result = _collapse_comparison.compare_modelos(after, after)
    assert result.status is _collapse_models.CheckStatus.FAILED
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
        _collapse_assessment_normalization,
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

    normalized = _collapse_assessment_normalization.normalized_assessment(tmp_path, assessment)

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
        _collapse_assessment_normalization,
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

    assert _collapse_assessment_normalization.normalized_assessment(tmp_path, assessment) is assessment


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
        _collapse_assessment_normalization,
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

    normalized = _collapse_assessment_normalization.normalized_assessment(tmp_path, assessment)

    assert normalized.minimal
    assert normalized.redundant_overrides == 0
    assert normalized.genuine_overrides == 0
    assert normalized.additions == 1
    assert normalized.by_revision_family[0]["redundant_overrides"] == 0
    assert normalized.by_revision_family[0]["additions"] == 1


@pytest.mark.parametrize("required_field", ["number", "section"])
def test_new_storage_row_still_requires_schema_fields(tmp_path: Path, required_field: str) -> None:
    modelo = load_modelo_directory(_build_modelo(tmp_path))
    payload = modelo.revisions["2025"].casillas[0].model_dump(mode="python")
    payload.pop(required_field)

    with pytest.raises(ValidationError, match=required_field):
        CasillaDefinition.model_validate(payload)


def test_tree_fingerprint_detects_changed_input(tmp_path: Path) -> None:
    source = _build_modelo(tmp_path)
    before = _collapse_fingerprints.fingerprint_tree(source)
    manifest = source / "manifest.toml"
    manifest.write_text(manifest.read_text(encoding="utf-8") + "\n", encoding="utf-8", newline="\n")

    after = _collapse_fingerprints.fingerprint_tree(source)

    assert before != after
    assert _collapse_fingerprints.fingerprint_digest(before) != _collapse_fingerprints.fingerprint_digest(after)


def test_request_matrix_includes_authored_and_global_boundary_coordinates(tmp_path: Path) -> None:
    modelo = load_modelo_directory(_build_modelo(tmp_path))

    matrix = _collapse_requests.request_matrix(modelo, floor=2023, ceiling=2026)

    cases = {item.case for item in matrix}
    assert {"exact", "valid_from", "valid_to", "support_floor", "support_ceiling"} <= cases


def test_assessment_fixture_contains_complete_member_and_nested_override_findings(tmp_path: Path) -> None:
    assessment: MigrationAssessment = assess_migration_state(_build_modelo(tmp_path))

    formula_findings = [item for item in assessment.unresolved_duplication if item.get("family") == "formulas"]
    assert any(len(_finding_fields(item)) > 1 for item in formula_findings)
    assert any("expression.literal" in _finding_fields(item) for item in formula_findings)


def test_published_authority_root_defaults_to_the_working_tree_publication(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(authority_staging.AUTHORITY_ROOT_ENV, raising=False)

    resolved = _collapse_fingerprints.published_authority_root()

    assert resolved == (REPO_ROOT / authority_staging.AUTHORING_AUTHORITY_DIRECTORY).resolve()
    assert resolved != (REPO_ROOT / "src" / "cadrumo" / "_data" / "registry" / "authority").resolve()


def test_published_authority_root_honours_the_environment_and_an_explicit_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configured = tmp_path / "configured-authority"
    explicit = tmp_path / "explicit-authority"
    monkeypatch.setenv(authority_staging.AUTHORITY_ROOT_ENV, str(configured))

    assert _collapse_fingerprints.published_authority_root() == configured.resolve()
    assert _collapse_fingerprints.published_authority_root(explicit) == explicit.resolve()


def test_optional_tree_fingerprint_detects_a_publication_appearing(tmp_path: Path) -> None:
    authority = tmp_path / "authority"
    before = _collapse_fingerprints.fingerprint_optional_tree(authority)
    authority.mkdir()
    (authority / "authority.current.json").write_text("{}\n", encoding="utf-8", newline="\n")

    after = _collapse_fingerprints.fingerprint_optional_tree(authority)

    assert before == ()
    assert before != after


def test_scoped_verification_refuses_an_unknown_modelo(tmp_path: Path) -> None:
    registry_root = tmp_path / "registry" / "aeat"
    _build_modelo(registry_root / "modelos")
    source_root = tmp_path / "data"
    source_root.mkdir()

    with pytest.raises(ValueError, match="unknown modelo identities requested: 000"):
        _collapse_run.run_registry_verification(
            registry_root=registry_root,
            source_root=source_root,
            work_dir=tmp_path / "work",
            authority_root=tmp_path / "authority",
            modelos=("000",),
        )


def test_first_difference_ignores_mapping_key_order_only() -> None:
    before = {"family_dispositions": {"projection_endpoints": {"cause": "a"}, "extraction_profiles": {"cause": "b"}}}
    after = {"family_dispositions": {"extraction_profiles": {"cause": "b"}, "projection_endpoints": {"cause": "a"}}}

    assert _collapse_comparison._first_difference(before, after) is None


def test_first_difference_detects_a_changed_mapping_key_set() -> None:
    before = {"family_dispositions": {"projection_endpoints": {}, "extraction_profiles": {}}}
    after = {"family_dispositions": {"projection_endpoints": {}}}

    difference = _collapse_comparison._first_difference(before, after)

    assert difference is not None
    assert difference["location"] == "$.family_dispositions"
    assert difference["reason"] == "mapping_keys_changed"


def test_first_difference_detects_a_value_change_under_reordered_keys() -> None:
    before = {"family_dispositions": {"projection_endpoints": {"cause": "a"}, "extraction_profiles": {"cause": "b"}}}
    after = {"family_dispositions": {"extraction_profiles": {"cause": "c"}, "projection_endpoints": {"cause": "a"}}}

    difference = _collapse_comparison._first_difference(before, after)

    assert difference is not None
    assert difference["location"] == "$.family_dispositions.extraction_profiles.cause"
    assert difference["reason"] == "value_changed"


def test_first_difference_still_detects_a_reordered_sequence() -> None:
    before = {"formulas": [{"id": "a"}, {"id": "b"}]}
    after = {"formulas": [{"id": "b"}, {"id": "a"}]}

    difference = _collapse_comparison._first_difference(before, after)

    assert difference is not None
    assert difference["location"] == "$.formulas[0].id"


def test_indexed_temporal_selection_composes_separately_stored_layouts() -> None:
    """Selection loads a base revision, so the verifier composes separate layouts before comparing.

    Comparing the source's complete selected revision with the indexed base
    revision alone reports layout-bearing coordinates as changed revisions.
    """
    from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

    with bundled_indexed_authority().operation() as operation:
        support = operation.supported_filing_years()
        bearing = next(
            (modelo_id, revision_id)
            for modelo_id, revision_id in sorted(operation.revision_ids())
            if operation.revision_with_export_layouts(modelo_id, revision_id).export_layouts
            and support.admits_filing_year(operation.revision(modelo_id, revision_id).valid_from.year)
            and operation.revision(modelo_id, revision_id).period_selector.declared_periods
        )
        modelo_id, revision_id = bearing
        base = operation.revision(modelo_id, revision_id)
        coordinate = _collapse_models.RequestCoordinate(
            filing_year=base.valid_from.year,
            period=str(base.period_selector.declared_periods[0]),
            on=None,
            revision_id=revision_id,
            case="layout-bearing",
        )

        result = _collapse_authority_queries._indexed_selection_result(operation, modelo_id, coordinate)

        assert result["outcome"] == "selected", result
        assert result["value"] == _collapse_comparison._typed_projection(
            _collapse_authority_queries._indexed_complete_revision(operation, modelo_id, revision_id)
        )
        assert result["value"] != _collapse_comparison._typed_projection(base)


def test_indexed_revision_and_snapshot_parity_include_form_layout_components(tmp_path: Path) -> None:
    """Separate SQLite form layouts survive comparison, and missing or changed layouts fail it."""
    from cadrumo.core.authority_grade import RegistryAuthorityGrade
    from cadrumo.domain.calculations.registry.authority import IndexedRegistryAuthority, ValidatedRegistryAuthority
    from dev.registry.pipeline.authority_publication import install_validated_authority_database

    from .test_authority_database import _artifact

    source_artifact = _artifact()
    source_modelo = source_artifact.modelos[0]
    source_revision = next(iter(source_modelo.revisions.values()))
    layout = FormLayoutDefinition(
        id="fixture-layout",
        revision_id=source_revision.id,
        seed_source="authored",
        generator_version=1,
        source_state_digest="a" * 64,
        placements=(
            FormPlacementDefinition(
                casilla_id=source_revision.casillas[0].id,
                kind="unplaced",
                unplaced_reason="pending_review",
            ),
        ),
    )
    source_revision = source_revision.model_copy(update={"form_layouts": (layout,)})
    source_modelo = source_modelo.model_copy(update={"revisions": {source_revision.id: source_revision}})
    source_artifact = replace(source_artifact, modelos=(source_modelo,))
    source_authority = ValidatedRegistryAuthority.from_validated_components(
        modelos=source_artifact.modelos,
        catalogues=source_artifact.catalogues,
        identity_digest=source_artifact.identity_digest,
        evidence=source_artifact.evidence,
        profile_schema=source_artifact.profile_schema,
    )
    coordinate = _collapse_models.RequestCoordinate(
        filing_year=2024,
        period="0A",
        on=None,
        revision_id=str(source_revision.id),
        case="layout-bearing",
    )
    source_snapshot = partial(source_authority.snapshot, grade=RegistryAuthorityGrade.CALCULATION)
    expected_snapshot = _collapse_authority_queries._snapshot_result(source_snapshot, "130", coordinate)
    assert expected_snapshot["outcome"] == "admitted", expected_snapshot
    expected_form_layouts = _collapse_comparison._typed_projection(source_revision.form_layouts)

    def snapshot_forms(value: object) -> tuple[object, object]:
        assert isinstance(value, Mapping)
        modelo = value["modelo"]
        revision = value["revision"]
        assert isinstance(modelo, Mapping)
        assert isinstance(revision, Mapping)
        revisions = modelo["revisions"]
        assert isinstance(revisions, Mapping)
        selected = revisions[str(source_revision.id)]
        assert isinstance(selected, Mapping)
        return revision["form_layouts"], selected["form_layouts"]

    expected_snapshot_forms = snapshot_forms(expected_snapshot["value"])

    variants = (
        ("present", (layout,), True),
        ("missing", (), False),
        ("changed", (layout.model_copy(update={"id": "changed-layout"}),), False),
    )
    for name, form_layouts, should_match in variants:
        variant_revision = source_revision.model_copy(update={"form_layouts": form_layouts})
        variant_modelo = source_modelo.model_copy(update={"revisions": {variant_revision.id: variant_revision}})
        artifact = replace(source_artifact, modelos=(variant_modelo,))
        destination = tmp_path / name
        install_validated_authority_database(artifact, destination=destination, require_current=lambda: None)
        indexed = IndexedRegistryAuthority(destination / "authority.current.json")
        try:
            with indexed.operation() as operation:
                selection = _collapse_authority_queries._indexed_selection_result(operation, "130", coordinate)
                indexed_snapshot = partial(operation.snapshot, grade=RegistryAuthorityGrade.CALCULATION)
                snapshot = _collapse_authority_queries._snapshot_result(
                    indexed_snapshot,
                    "130",
                    coordinate,
                    indexed_form_layout=operation.form_layout,
                )
                assert selection["outcome"] == "selected", selection
                assert snapshot["outcome"] == "admitted", snapshot
                selection_value = selection["value"]
                snapshot_value = snapshot["value"]
                assert isinstance(selection_value, Mapping)
                assert isinstance(snapshot_value, Mapping)
                actual_snapshot_forms = snapshot_forms(snapshot_value)
                revision_difference = _collapse_comparison._first_difference(
                    expected_form_layouts,
                    selection_value.get("form_layouts"),
                    "$.selection.value.form_layouts",
                )
                snapshot_difference = _collapse_comparison._first_difference(
                    expected_snapshot_forms,
                    actual_snapshot_forms,
                    "$.snapshot.value.form_layouts",
                )
                assert (revision_difference is None) is should_match, revision_difference
                assert (snapshot_difference is None) is should_match, snapshot_difference
                if not should_match:
                    assert "form_layouts" in str(revision_difference)
                    assert "form_layouts" in str(snapshot_difference)
        finally:
            indexed.close()


def test_real_modelo_131_snapshot_parity_preserves_raw_and_effective_export_layouts(
    registry_authority: ValidatedRegistryAuthority,
    tmp_path: Path,
) -> None:
    """Form composition preserves declared exports beside binding-derived snapshot exports."""
    from cadrumo.domain.calculations.registry.authority import IndexedRegistryAuthority
    from cadrumo.domain.calculations.registry.authority_artifact import AuthorityArtifact
    from dev.registry.compiler.identity import resolve_registry_identity
    from dev.registry.compiler.loader_fingerprints import collect_registry_tree_fingerprints
    from dev.registry.pipeline.authority_publication import install_validated_authority_database

    registry_root = bundled_path("registry", "aeat")
    identity = resolve_registry_identity(registry_root, collect_fingerprints=collect_registry_tree_fingerprints)
    artifact = AuthorityArtifact(
        modelos=registry_authority.modelos,
        catalogues=registry_authority.catalogues,
        identity_digest=identity.digest,
        evidence=registry_authority.evidence,
        profile_schema=registry_authority.profile_schema(),
    )
    indexed_root = tmp_path / "indexed"
    install_validated_authority_database(artifact, destination=indexed_root, require_current=lambda: None)
    indexed_authority = IndexedRegistryAuthority(indexed_root / "authority.current.json")

    coordinate = _collapse_models.RequestCoordinate(
        filing_year=2022,
        period="1T",
        on=None,
        revision_id="2019-2023",
        case="source-index-form-layout",
    )
    source = _collapse_authority_queries._snapshot_result(registry_authority.snapshot, "131", coordinate)
    assert source["outcome"] == "admitted", source
    source_value = source["value"]
    assert isinstance(source_value, Mapping)

    try:
        with indexed_authority.operation() as operation:
            indexed = _collapse_authority_queries._snapshot_result(
                operation.snapshot,
                "131",
                coordinate,
                indexed_form_layout=operation.form_layout,
            )
    finally:
        indexed_authority.close()
    assert indexed["outcome"] == "admitted", indexed
    indexed_value = indexed["value"]
    assert isinstance(indexed_value, Mapping)

    def layout_field_counts(value: Mapping[str, object]) -> tuple[tuple[int, ...], ...]:
        layouts = value["export_layouts"]
        assert isinstance(layouts, list)
        counts: list[tuple[int, ...]] = []
        for layout in layouts:
            assert isinstance(layout, Mapping)
            records = layout["records"]
            assert isinstance(records, list)
            record_counts: list[int] = []
            for record in records:
                assert isinstance(record, Mapping)
                fields = record["fields"]
                assert isinstance(fields, list)
                record_counts.append(len(fields))
            counts.append(tuple(record_counts))
        return tuple(counts)

    def selected_projection(value: Mapping[str, object]) -> tuple[Mapping[str, object], Mapping[str, object]]:
        modelo = value["modelo"]
        revision = value["revision"]
        assert isinstance(modelo, Mapping)
        assert isinstance(revision, Mapping)
        revisions = modelo["revisions"]
        assert isinstance(revisions, Mapping)
        selected = revisions["2019-2023"]
        assert isinstance(selected, Mapping)
        return cast(Mapping[str, object], selected), cast(Mapping[str, object], revision)

    source_model_revision, source_effective_revision = selected_projection(source_value)
    indexed_model_revision, indexed_effective_revision = selected_projection(indexed_value)
    source_declared_counts = layout_field_counts(source_model_revision)
    source_effective_counts = layout_field_counts(source_effective_revision)
    indexed_declared_counts = layout_field_counts(indexed_model_revision)
    indexed_effective_counts = layout_field_counts(indexed_effective_revision)

    # The authored 131 layout now explicitly includes all producer fields, so
    # derivation need not increase the field count. Compare each representation
    # to its owner rather than requiring an incomplete declared layout.
    from cadrumo.domain.calculations.registry.export import derive_export_layouts_from_bindings

    declared_revision = next(modelo for modelo in registry_authority.modelos if modelo.id == "131").revisions[
        "2019-2023"
    ]
    assert source_declared_counts == tuple(
        tuple(len(record.fields) for record in layout.records) for layout in declared_revision.export_layouts
    )
    assert source_effective_counts == tuple(
        tuple(len(record.fields) for record in layout.records)
        for layout in derive_export_layouts_from_bindings(declared_revision)
    )
    assert indexed_declared_counts == source_declared_counts
    assert indexed_effective_counts == source_effective_counts
    assert source_effective_revision["form_layouts"]
    assert source_model_revision["form_layouts"] == source_effective_revision["form_layouts"]
    assert indexed_model_revision["form_layouts"] == source_model_revision["form_layouts"]
    assert _collapse_comparison._first_difference(source_value, indexed_value) is None


def test_snapshot_comparison_ignores_unselected_editions_but_not_the_selected_one() -> None:
    """The indexed runtime scopes a snapshot's modelo to the edition it selected.

    An in-memory authority keeps every edition there. Editions the snapshot did
    not select carry none of its meaning, so they must not register as a
    difference, while any change to the selected edition still must.
    """
    from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

    with bundled_indexed_authority().operation() as operation:
        support = operation.supported_filing_years()
        directory = operation.modelo_directory("100")
        editions = sorted(str(revision.id) for revision in directory.revisions)
        snapshot = operation.snapshot("100", filing_year=support.floor, period="0A")
        other_id = next(revision_id for revision_id in editions if revision_id != str(snapshot.revision.id))
        other = operation.revision("100", other_id)
    widened = snapshot.model_copy(
        update={
            "modelo": snapshot.modelo.model_copy(
                update={"revisions": {**snapshot.modelo.revisions, other.id: other}},
            )
        }
    )
    changed = snapshot.model_copy(update={"revision": snapshot.revision.model_copy(update={"parameters": ()})})
    coordinate = _collapse_models.RequestCoordinate(
        filing_year=support.floor, period="0A", on=None, revision_id=None, case="floor"
    )

    def result(value: object) -> object:
        return _collapse_authority_queries._snapshot_result(lambda *_args, **_kwargs: value, "100", coordinate)

    assert _collapse_comparison._first_difference(result(snapshot), result(widened), "$") is None
    assert _collapse_comparison._first_difference(result(snapshot), result(changed), "$") is not None


def _unresolved_rows(modelo_dir: Path) -> list[Mapping[str, object]]:
    return [
        row
        for row in _collapse_roots.root_eligibility(modelo_dir)
        if row["status"] is _collapse_models.RootEligibility.UNRESOLVED
    ]


def _schedule_defaulted_modelo(tmp_path: Path) -> Path:
    """A copied modelo whose filing schedules take their source refs from the edition default."""
    modelos = bundled_path("registry", "aeat", "modelos")
    for modelo_dir in sorted(modelos.iterdir()):
        manifests = sorted((modelo_dir / "revisions").glob("*/revision.toml"))
        if any("\nfiling_schedule_source_refs = " in manifest.read_text(encoding="utf-8") for manifest in manifests):
            target = tmp_path / modelo_dir.name
            shutil.copytree(modelo_dir, target)
            return target
    raise LookupError("no modelo grounds its filing schedules through the edition default")


def test_root_eligibility_binds_the_filing_schedule_source_default(tmp_path: Path) -> None:
    """A schedule relying on its edition's source default is resolved, as the loader resolves it."""
    assert _unresolved_rows(_schedule_defaulted_modelo(tmp_path)) == []


def test_root_eligibility_still_refuses_a_schedule_left_without_any_source(tmp_path: Path) -> None:
    modelo_dir = _schedule_defaulted_modelo(tmp_path)
    for manifest in sorted((modelo_dir / "revisions").glob("*/revision.toml")):
        text = manifest.read_text(encoding="utf-8")
        manifest.write_text(
            "\n".join(line for line in text.splitlines() if not line.startswith("filing_schedule_source_refs = "))
            + "\n",
            encoding="utf-8",
        )

    assert _unresolved_rows(modelo_dir)
