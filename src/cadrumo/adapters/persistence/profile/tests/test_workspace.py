"""Integration contracts for the Workspace V1 WORK-then-REGISTRY capture core."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.application.modelo.workspace import (
    STATIC_INSPECTION_WORK_REVIEW_FACET,
    modelo_work_selector_request_for_target,
)
from cadrumo.application.modelo.workspace_models import (
    ModeloWorkspaceBoundedFacetV1,
    ModeloWorkspaceCapabilityDisposition,
    ModeloWorkspaceFacetName,
    ModeloWorkspaceRevisionAssertionDisposition,
    ModeloWorkspaceRevisionAssertionSource,
    ModeloWorkspaceSchemaRecordV1,
)
from cadrumo.application.modelo.workspace_schema import (
    ModeloWorkspaceStaleCursorError,
    binding_schema_records,
    fold_slots,
    formula_operand_references_for_casilla,
    formula_schema_records,
    paginate_modelo_workspace_facet,
    parameter_schema_records,
    relation_source_endpoints_for_casilla,
    relation_target_endpoints_for_binding,
    resolve_static_inspection_schema_identity,
    static_inspection_casilla_schema_records,
    static_inspection_contributors,
    static_inspection_evidence_horizon,
    static_inspection_family_dispositions,
    static_inspection_schema_records,
)
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.period import Period
from cadrumo.core.schema_family_disposition import RegistrySchemaFamilyDisposition
from cadrumo.domain.calculations.registry.authority import (
    PinnedAuthorityOperation,
)
from cadrumo.domain.calculations.registry.tests.published_authority import (
    published_snapshot,
)

from .published_authority_support import published_authority_operation
from .workspace_support import (
    FILING_YEAR,
    LAW_SELECTED_REVISION_ID,
    assemble_static_inspection_pieces,
    real_303_inspection,
    real_inspection,
    seed_work_unit,
    supported_filing_years,
    visible_target,
)
from .workspace_support import (
    workspace_repos as workspace_repos,
)

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.static_inspection import RegistryRevisionInspection

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


def test_visible_target_projects_into_a_selector_request_with_no_exact_operands() -> None:
    """The visible-target mapping must carry natural coordinates, not an exact work-unit lookup."""
    target = visible_target("some-bucket", revision_id=LAW_SELECTED_REVISION_ID)

    request = modelo_work_selector_request_for_target(target, bucket_id="some-bucket")

    assert request.modelo == "130"
    assert request.filing_year == FILING_YEAR
    assert request.revision_id == LAW_SELECTED_REVISION_ID
    assert request.bucket_id == "some-bucket"
    assert request.work_unit_id is None
    assert request.has_visible_target
    assert not request.has_exact_target


def test_formula_operand_references_answer_the_input_direction_not_the_output_direction() -> None:
    """A real revision where the same casilla is both a formula's output and another's input."""
    authority = published_authority_operation()
    snapshot = authority.snapshot("130", filing_year=FILING_YEAR, period="1T")
    formulas = snapshot.revision.formulas

    producing_formula_ids = {formula.id for formula in formulas if formula.target_casilla_id == "03"}
    assert producing_formula_ids == {"modelo-130-rendimiento-neto"}

    consuming = formula_operand_references_for_casilla(formulas, "03")

    assert len(consuming) == 1
    assert consuming[0].formula_id == "modelo-130-pago-fraccionado-directa"
    assert consuming[0].casilla_id == "03"
    # The producing formula must never appear as a "consumer of its own output"
    # unless its own expression genuinely reads casilla 03 as an operand.
    assert consuming[0].formula_id not in producing_formula_ids


_RELATION_BINDING_ID = "renta-modelo-131-pagos-fraccionados"


_RELATION_SOURCE_MODELO = "131"


_RELATION_SOURCE_CASILLA_ID = "15"


def _relation_fold_filing_year() -> int:
    """Return the newest supported filing year whose Renta revision declares the fold."""
    for year in sorted(supported_filing_years(), reverse=True):
        bindings = published_snapshot("100", filing_year=year, period="0A").revision.bindings
        if any(binding_id == _RELATION_BINDING_ID for binding_id, _provider in fold_slots(bindings)):
            return year
    raise AssertionError("no supported filing year declares the Modelo 131 pagos fold")


_RELATION_FILING_YEAR = _relation_fold_filing_year()


def test_relation_source_endpoint_matches_the_registrys_own_source_casilla_field() -> None:
    authority = published_authority_operation()
    snapshot = authority.reading_snapshot("100", filing_year=_RELATION_FILING_YEAR, period="0A")
    bindings = snapshot.revision.bindings
    assert bindings  # sanity: this fixture coordinate carries a real fold slot

    endpoints = relation_source_endpoints_for_casilla(
        bindings, _RELATION_SOURCE_CASILLA_ID, source_modelo=_RELATION_SOURCE_MODELO
    )

    assert len(endpoints) == 1
    assert endpoints[0].relation_id == _RELATION_BINDING_ID
    assert endpoints[0].casilla_id == _RELATION_SOURCE_CASILLA_ID

    # A different casilla id must never match.
    assert (
        relation_source_endpoints_for_casilla(bindings, "not-the-source-casilla", source_modelo=_RELATION_SOURCE_MODELO)
        == ()
    )
    # Nor may the same casilla id of a different modelo.
    assert relation_source_endpoints_for_casilla(bindings, _RELATION_SOURCE_CASILLA_ID, source_modelo="100") == ()


def test_relation_target_endpoint_matches_the_registrys_own_target_binding_field() -> None:
    authority = published_authority_operation()
    snapshot = authority.reading_snapshot("100", filing_year=_RELATION_FILING_YEAR, period="0A")
    bindings = snapshot.revision.bindings

    endpoints = relation_target_endpoints_for_binding(bindings, _RELATION_BINDING_ID)

    assert len(endpoints) == 1
    assert endpoints[0].relation_id == _RELATION_BINDING_ID
    assert endpoints[0].binding_id == _RELATION_BINDING_ID

    # The relation's own SOURCE casilla id must never be accepted as a target binding.
    assert relation_target_endpoints_for_binding(bindings, _RELATION_SOURCE_CASILLA_ID) == ()


def test_static_inspection_schema_identity_is_stable_and_uses_the_s278_manifest_digest() -> None:
    """schema_identity must use the generated-manifest digest, never the completeness manifest's."""
    from cadrumo.application.modelo.workspace_manifest import generate_modelo_workspace_field_manifest_for_inspection
    from cadrumo.domain.calculations.registry.static_inspection import RegistryRevisionInspection

    authority = published_authority_operation()
    capture = authority.capture_law_selected_projection("130", filing_year=FILING_YEAR, period="1T")
    inspection = capture.projection
    assert isinstance(inspection, RegistryRevisionInspection)

    identity = resolve_static_inspection_schema_identity(inspection)
    identity_again = resolve_static_inspection_schema_identity(inspection)

    assert identity == identity_again
    assert identity.schema_id == f"modelo-130-{LAW_SELECTED_REVISION_ID}"
    assert (
        identity.field_manifest_digest
        == generate_modelo_workspace_field_manifest_for_inspection(inspection).manifest_digest
    )


def test_static_inspection_evidence_horizon_is_stable_and_sourced_from_the_inspection() -> None:
    authority = published_authority_operation()
    capture = authority.capture_law_selected_projection("130", filing_year=FILING_YEAR, period="1T")
    inspection = capture.projection
    from cadrumo.domain.calculations.registry.static_inspection import RegistryRevisionInspection

    assert isinstance(inspection, RegistryRevisionInspection)

    horizon = static_inspection_evidence_horizon(inspection)
    horizon_again = static_inspection_evidence_horizon(inspection)

    assert horizon == horizon_again
    assert set(horizon.source_refs) == inspection.source_ref_ids
    assert horizon.source_refs == tuple(sorted(horizon.source_refs))


def test_static_inspection_contributors_are_exactly_the_four_admission_reads() -> None:
    contributors = static_inspection_contributors()

    assert len(contributors) == 4
    assert len({(c.owner, c.producer) for c in contributors}) == 4
    # Sorted, per the shared contributor-tuple ordering rule.
    assert contributors == tuple(sorted(contributors, key=lambda c: (c.owner, c.producer)))


def test_static_inspection_work_review_facet_is_unmeasured_with_no_review() -> None:
    assert STATIC_INSPECTION_WORK_REVIEW_FACET.disposition == ModeloWorkspaceCapabilityDisposition.UNMEASURED
    assert STATIC_INSPECTION_WORK_REVIEW_FACET.review is None


def test_static_inspection_casilla_schema_records_use_the_s277_joins_and_s283_absence() -> None:
    from cadrumo.core.external_constants import OutputLanguage

    authority = published_authority_operation()
    capture = authority.capture_law_selected_projection("130", filing_year=FILING_YEAR, period="1T")
    from cadrumo.domain.calculations.registry.static_inspection import RegistryRevisionInspection

    inspection = capture.projection
    assert isinstance(inspection, RegistryRevisionInspection)

    from cadrumo.application.modelo.workspace_models import (
        ModeloWorkspaceResolvedTargetV1,
        ModeloWorkspaceRevisionAssertionV1,
    )

    # A minimal, directly constructed resolved target is legitimate here: this
    # test targets record construction from the inspection, not the capture
    # ordering already proven elsewhere.
    target = ModeloWorkspaceResolvedTargetV1(
        bucket_id="test-bucket-0000-0000-0000-000000000000",
        modelo="130",
        filing_year=FILING_YEAR,
        period=Period.from_year_and_code(FILING_YEAR, "1T"),
        law_selected_revision_id=LAW_SELECTED_REVISION_ID,
        review_status=inspection.review_status,
        requested_revision_assertion=ModeloWorkspaceRevisionAssertionV1(
            source=ModeloWorkspaceRevisionAssertionSource.REQUESTED,
            disposition=ModeloWorkspaceRevisionAssertionDisposition.NOT_PRESENT,
            asserted_revision_id=None,
        ),
        stored_revision_assertion=ModeloWorkspaceRevisionAssertionV1(
            source=ModeloWorkspaceRevisionAssertionSource.STORED,
            disposition=ModeloWorkspaceRevisionAssertionDisposition.NOT_PRESENT,
            asserted_revision_id=None,
        ),
    )

    from cadrumo.application.modelo.workspace_models import (
        ModeloWorkspaceCasillaReferenceV1,
        ModeloWorkspaceLocalizedTextV1,
    )

    records = static_inspection_casilla_schema_records(inspection, target, output_language=OutputLanguage.ES)

    casilla_ids: list[str] = []
    for record in records:
        assert isinstance(record.reference, ModeloWorkspaceCasillaReferenceV1)
        casilla_ids.append(record.reference.casilla_id)
        assert record.legal_refs is None
        assert record.constraints is None
        assert isinstance(record.label, ModeloWorkspaceLocalizedTextV1)
        assert record.label.value  # a real, non-empty label was resolved

    assert len(records) == len(inspection.casilla_ids)
    assert casilla_ids == sorted(inspection.casilla_ids)

    by_id = {casilla_id: record for casilla_id, record in zip(casilla_ids, records, strict=True)}
    label = by_id["03"].label
    assert isinstance(label, ModeloWorkspaceLocalizedTextV1)
    assert label.value == "Rendimiento neto"
    assert any(op.formula_id == "modelo-130-pago-fraccionado-directa" for op in by_id["03"].formula_operands)


def test_schema_facet_pagination_round_trips_a_cursor_across_all_pages(
    workspace_repos: tuple[str, WorkUnitCatalogueRepository], *, operation: PinnedAuthorityOperation
) -> None:
    from cadrumo.core.external_constants import OutputLanguage

    bucket_id, repository = workspace_repos
    seed_work_unit(repository, bucket_id=bucket_id, operation=operation)
    inspection, target, schema_identity, baseline, contributors = assemble_static_inspection_pieces(
        bucket_id, repository
    )
    records = static_inspection_casilla_schema_records(inspection, target, output_language=OutputLanguage.ES)
    assert len(records) > 4  # sanity: enough real records to page over more than once

    collected = []
    cursor = None
    pages = 0
    while True:
        page = paginate_modelo_workspace_facet(
            ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceSchemaRecordV1],
            records,
            facet=ModeloWorkspaceFacetName.SCHEMA,
            target=target,
            schema_identity=schema_identity,
            baseline=baseline,
            contributors=contributors,
            disposition=ModeloWorkspaceCapabilityDisposition.AVAILABLE,
            page_size=3,
            cursor=cursor,
        )
        pages += 1
        collected.extend(page.records)
        assert len(page.records) <= 3
        assert page.has_more == (page.next_cursor is not None)
        if page.next_cursor is None:
            break
        cursor = page.next_cursor

    assert pages > 1
    assert tuple(collected) == records


def test_schema_facet_stale_cursor_refuses_rather_than_returning_a_different_page(
    workspace_repos: tuple[str, WorkUnitCatalogueRepository], *, operation: PinnedAuthorityOperation
) -> None:
    from cadrumo.core.external_constants import OutputLanguage

    bucket_id, repository = workspace_repos
    seed_work_unit(repository, bucket_id=bucket_id, operation=operation)
    inspection, target, schema_identity, baseline, contributors = assemble_static_inspection_pieces(
        bucket_id, repository
    )
    records = static_inspection_casilla_schema_records(inspection, target, output_language=OutputLanguage.ES)

    first_page = paginate_modelo_workspace_facet(
        ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceSchemaRecordV1],
        records,
        facet=ModeloWorkspaceFacetName.SCHEMA,
        target=target,
        schema_identity=schema_identity,
        baseline=baseline,
        contributors=contributors,
        disposition=ModeloWorkspaceCapabilityDisposition.AVAILABLE,
        page_size=3,
    )
    assert first_page.next_cursor is not None
    # Simulate a real ABA-style move: the same coordinate re-observed after
    # the underlying contributor generation advanced (a distinct
    # contributor_epoch_digest is exactly what that produces). The baseline's
    # own model has no cross-field validator tying contributor_epoch_digest to
    # anything else, so this is a legitimate "moved" baseline, not a
    # structurally-invalid one.
    moved_baseline = baseline.model_copy(update={"contributor_epoch_digest": "9" * 64})

    with pytest.raises(ModeloWorkspaceStaleCursorError):
        paginate_modelo_workspace_facet(
            ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceSchemaRecordV1],
            records,
            facet=ModeloWorkspaceFacetName.SCHEMA,
            target=target,
            schema_identity=schema_identity,
            baseline=moved_baseline,
            contributors=contributors,
            disposition=ModeloWorkspaceCapabilityDisposition.AVAILABLE,
            page_size=3,
            cursor=first_page.next_cursor,
        )


def _real_100_inspection() -> RegistryRevisionInspection:
    return real_inspection("100", filing_year=_RELATION_FILING_YEAR, period="0A")


def _real_303_snapshot():
    from cadrumo.domain.calculations.registry.schema import RegistrySnapshot

    authority = published_authority_operation()
    capture = authority.capture_law_selected_projection(
        "303", filing_year=FILING_YEAR, period="1T", grade=RegistryAuthorityGrade.CALCULATION
    )
    snapshot = capture.projection
    assert isinstance(snapshot, RegistrySnapshot)
    return snapshot


def test_shared_schema_record_builders_are_identical_whether_fed_inspection_or_snapshot() -> None:
    """The shared BINDING/FORMULA/RELATION/PARAMETER builders cannot drift between admissions.

    Both admissions resolve the same modelo/filing_year/period, so
    ``inspection.bindings``/``.formulas``/``.relations``/``.parameters`` and
    ``snapshot.revision.bindings``/etc. must be the same registry-declared
    data -- proving the shared builders produce byte-identical output either
    way is the guarantee that a graded and a static read cannot disagree
    about the same revision's edges.
    """
    inspection = real_303_inspection()
    snapshot = _real_303_snapshot()
    revision = snapshot.revision

    inspection_bindings = binding_schema_records(inspection.binding_ids, inspection.bindings)
    snapshot_binding_ids = frozenset(binding.id for binding in revision.bindings)
    snapshot_bindings = binding_schema_records(snapshot_binding_ids, revision.bindings)
    assert inspection_bindings == snapshot_bindings
    assert len(inspection_bindings) > 0

    inspection_formulas = formula_schema_records(inspection.formulas)
    snapshot_formulas = formula_schema_records(revision.formulas)
    assert inspection_formulas == snapshot_formulas
    assert len(inspection_formulas) > 0

    inspection_parameters = parameter_schema_records(inspection.parameters, inspection.formulas)
    snapshot_parameters = parameter_schema_records(revision.parameters, revision.formulas)
    assert inspection_parameters == snapshot_parameters
    assert len(inspection_parameters) > 0


def test_static_inspection_binding_schema_records_use_the_real_binding_definitions() -> None:
    from cadrumo.application.modelo.workspace_models import (
        ModeloWorkspaceBindingReferenceV1,
        ModeloWorkspaceTechnicalLabelV1,
    )

    inspection = _real_100_inspection()
    records = binding_schema_records(inspection.binding_ids, inspection.bindings)

    assert len(records) == len(inspection.binding_ids)
    binding_ids = []
    for record in records:
        assert isinstance(record.reference, ModeloWorkspaceBindingReferenceV1)
        binding_ids.append(record.reference.binding_id)
        assert isinstance(record.label, ModeloWorkspaceTechnicalLabelV1)
        assert record.label.identifier == record.reference.binding_id
        assert record.legal_refs is not None  # BindingDefinition is retained whole
        assert record.constraints == ()
    assert binding_ids == sorted(inspection.binding_ids)
    definitions = {binding.id: binding for binding in inspection.bindings}
    # Every binding declares at least one source reference, so an empty tuple
    # here would mean the record dropped it rather than that none exists.
    for binding_id, record in zip(binding_ids, records, strict=True):
        definition = definitions[binding_id]
        assert record.source_refs == tuple(definition.source_refs)
        assert record.source_refs

    by_id = dict(zip(binding_ids, records, strict=True))
    assert any(
        endpoint.relation_id == _RELATION_BINDING_ID for endpoint in by_id[_RELATION_BINDING_ID].relation_endpoints
    )


def test_static_inspection_formula_schema_records_carry_their_own_full_operand_set() -> None:
    from cadrumo.application.modelo.workspace_models import (
        ModeloWorkspaceFormulaReferenceV1,
        ModeloWorkspaceTechnicalLabelV1,
    )

    inspection = real_303_inspection()
    records = formula_schema_records(inspection.formulas)

    assert len(records) == len(inspection.formulas)
    for record in records:
        assert isinstance(record.reference, ModeloWorkspaceFormulaReferenceV1)
        assert isinstance(record.label, ModeloWorkspaceTechnicalLabelV1)
        assert record.label.identifier == record.reference.formula_id
        assert record.legal_refs is not None


def test_static_inspection_parameter_schema_records_key_off_dispatching_formulas() -> None:
    from cadrumo.application.modelo.workspace_models import ModeloWorkspaceParameterReferenceV1

    inspection = real_303_inspection()
    records = parameter_schema_records(inspection.parameters, inspection.formulas)

    assert len(records) == len(inspection.parameters)
    for record in records:
        assert isinstance(record.reference, ModeloWorkspaceParameterReferenceV1)
        assert record.legal_refs is not None


def test_static_inspection_schema_records_project_four_reference_kinds_and_relation_endpoints_deterministically() -> (
    None
):
    from cadrumo.core.external_constants import OutputLanguage

    inspection = _real_100_inspection()
    target = _minimal_resolved_target(inspection, modelo="100", filing_year=_RELATION_FILING_YEAR, period="0A")

    records = static_inspection_schema_records(inspection, target, output_language=OutputLanguage.ES)
    records_again = static_inspection_schema_records(inspection, target, output_language=OutputLanguage.ES)

    expected_total = (
        len(inspection.casilla_ids)
        + len(inspection.binding_ids)
        + len(inspection.formulas)
        + len(inspection.parameters)
    )
    assert len(records) == expected_total
    assert records == records_again  # deterministic ordering across identical repeated reads

    kinds = {record.reference.kind for record in records}
    assert kinds == {"casilla", "binding", "formula", "parameter"}

    relation_folds = fold_slots(inspection.bindings)
    # Every fold here reads another modelo, so its source casillas never
    # belong to this schema; only a self-sourced fold would contribute.
    expected_sources = tuple(
        (binding_id, source_casilla_id)
        for binding_id, provider in relation_folds
        if str(provider.source_modelo) == "100"
        for source_casilla_id in provider.declared_source_casilla_ids
    )
    expected_targets = tuple((binding_id, binding_id) for binding_id, _provider in relation_folds)
    actual_sources = tuple(
        (endpoint.relation_id, endpoint.casilla_id)
        for record in records
        for endpoint in record.relation_endpoints
        if endpoint.kind == "relation_source_casilla"
    )
    actual_targets = tuple(
        (endpoint.relation_id, endpoint.binding_id)
        for record in records
        for endpoint in record.relation_endpoints
        if endpoint.kind == "relation_target_binding"
    )
    assert any(str(provider.source_modelo) != "100" for _binding_id, provider in relation_folds)
    assert expected_targets
    assert sorted(actual_sources) == sorted(expected_sources)
    assert sorted(actual_targets) == sorted(expected_targets)


def _minimal_resolved_target(inspection, *, modelo: str = "303", filing_year: int = FILING_YEAR, period: str = "1T"):
    from cadrumo.application.modelo.workspace_models import (
        ModeloWorkspaceResolvedTargetV1,
        ModeloWorkspaceRevisionAssertionV1,
    )

    return ModeloWorkspaceResolvedTargetV1(
        bucket_id="test-bucket-0000-0000-0000-000000000000",
        modelo=modelo,
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, period),
        law_selected_revision_id=inspection.revision_id,
        review_status=inspection.review_status,
        requested_revision_assertion=ModeloWorkspaceRevisionAssertionV1(
            source=ModeloWorkspaceRevisionAssertionSource.REQUESTED,
            disposition=ModeloWorkspaceRevisionAssertionDisposition.NOT_PRESENT,
            asserted_revision_id=None,
        ),
        stored_revision_assertion=ModeloWorkspaceRevisionAssertionV1(
            source=ModeloWorkspaceRevisionAssertionSource.STORED,
            disposition=ModeloWorkspaceRevisionAssertionDisposition.NOT_PRESENT,
            asserted_revision_id=None,
        ),
    )


def test_static_inspection_family_dispositions_reports_only_declared_not_applicable_families() -> None:
    inspection = real_inspection("111", filing_year=FILING_YEAR, period="1T")

    dispositions = static_inspection_family_dispositions(inspection)

    assert len(dispositions) == len(inspection.family_dispositions)
    by_family = {d.family: d for d in dispositions}
    assert "parameters" in by_family
    for family, declaration in inspection.family_dispositions.items():
        assert by_family[family].disposition == RegistrySchemaFamilyDisposition.NOT_APPLICABLE
        assert by_family[family].legal_refs == declaration.legal_refs
        assert by_family[family].source_refs == declaration.source_refs
    # A family the inspection has no data for at all (e.g. "constructs") is
    # never reported here -- reporting nothing is honest, guessing is not.
    assert "constructs" not in by_family


def test_static_inspection_does_not_report_populated_applicability_as_not_applicable() -> None:
    inspection = real_303_inspection()

    assert _real_303_snapshot().revision.applicability
    assert "applicability" not in inspection.family_dispositions
    assert "applicability" not in {item.family for item in static_inspection_family_dispositions(inspection)}
