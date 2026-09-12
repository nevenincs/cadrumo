"""Integration contracts for the Workspace V1 WORK-then-REGISTRY capture core."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from ....domain.calculations.registry.static_inspection import RegistryRevisionInspection

from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....core.aggregation import BindingSourceKind
from ....core.period import Period
from ....core.schema_family_disposition import RegistrySchemaFamilyDisposition
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.modelos.work_unit import WorkUnit
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.secure_sql import isolated_runtime_profile
from ..work_addressing import ModeloVisibleFilingTarget
from ..work_lifecycle import create_work_unit
from ..workspace import (
    STATIC_INSPECTION_WORK_REVIEW_FACET,
    ModeloWorkspaceStaleCursorError,
    binding_schema_records,
    capture_modelo_workspace_locale_summary,
    capture_modelo_workspace_target_captures,
    formula_operand_references_for_casilla,
    formula_schema_records,
    modelo_work_selector_request_for_target,
    paginate_modelo_workspace_facet,
    parameter_schema_records,
    relation_schema_records,
    relation_source_endpoints_for_casilla,
    relation_target_endpoints_for_binding,
    resolve_static_inspection_baseline,
    resolve_static_inspection_result,
    resolve_static_inspection_schema_identity,
    static_inspection_casilla_schema_records,
    static_inspection_contributors,
    static_inspection_evidence_horizon,
    static_inspection_family_dispositions,
    static_inspection_schema_records,
)
from ..workspace_models import (
    ModeloWorkspaceBoundedFacetV1,
    ModeloWorkspaceCapabilityDisposition,
    ModeloWorkspaceCapabilityName,
    ModeloWorkspaceFacetName,
    ModeloWorkspaceMaterializationRecordV1,
    ModeloWorkspaceRevisionAssertionDisposition,
    ModeloWorkspaceRevisionAssertionSource,
    ModeloWorkspaceScalarMaterializationRecordV1,
    ModeloWorkspaceScalarMaterializationV1,
    ModeloWorkspaceSchemaRecordV1,
    ModeloWorkspaceVisibleFilingTargetV1,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_WORKSPACE_PROFILE_ID = "13000000-0000-4000-8000-000000000231"
_T0 = datetime(2026, 6, 5, 9, 0, 0, tzinfo=UTC)
_LAW_SELECTED_REVISION_ID = "2019-y-siguientes"
_READY_PROFILE_FACTS: tuple[UserProfileFact, ...] = (
    UserProfileFact(path="identity.tax_id", value="00000000T"),
    UserProfileFact(path="identity.name", value="Test Operator"),
    UserProfileFact(path="identity.surnames", value="Workspace"),
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="activities.description", value="economic activity"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="iva.m303_regime_composition", value="general"),
    UserProfileFact(path="iva.redeme_enrolled", value=False),
    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
    UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
    UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
    UserProfileFact(path="provenance.source", value="manual_cli"),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
)


def _seed_ready_profile(objects: SecureObjectRepository, *, bucket_id: str) -> None:
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=bucket_id,
            facts=_READY_PROFILE_FACTS,
            created_at=_T0,
            updated_at=_T0,
        ),
    )


@pytest.fixture
def workspace_repos(tmp_path: Path) -> Iterator[tuple[str, WorkUnitCatalogueRepository]]:
    """Yield one real bucket-scoped work-unit repository over an isolated profile."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_WORKSPACE_PROFILE_ID) as profile:
        _seed_ready_profile(profile.repository, bucket_id=profile.bucket_id)
        yield profile.bucket_id, WorkUnitCatalogueRepository(objects=profile.repository)


def _seed_work_unit(
    repository: WorkUnitCatalogueRepository,
    *,
    bucket_id: str,
    revision_id: str = _LAW_SELECTED_REVISION_ID,
) -> WorkUnit:
    return create_work_unit(
        bucket_id=bucket_id,
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id=revision_id,
        repository=repository,
        clock=_T0,
    )


def _visible_target(bucket_id: str, *, revision_id: str | None = None) -> ModeloWorkspaceVisibleFilingTargetV1:
    return ModeloWorkspaceVisibleFilingTargetV1(
        target=ModeloVisibleFilingTarget(
            modelo="130",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            registry_revision_id=revision_id,
            bucket_id=bucket_id,
        ),
    )


def _visible_target_for(
    modelo: str,
    *,
    filing_year: int,
    period: str,
    bucket_id: str,
    revision_id: str | None = None,
) -> ModeloWorkspaceVisibleFilingTargetV1:
    return ModeloWorkspaceVisibleFilingTargetV1(
        target=ModeloVisibleFilingTarget(
            modelo=modelo,
            filing_year=filing_year,
            period=Period.from_year_and_code(filing_year, period),
            registry_revision_id=revision_id,
            bucket_id=bucket_id,
        ),
    )


def _corrupt_stored_revision(
    repository: WorkUnitCatalogueRepository,
    work_unit: WorkUnit,
    *,
    corrupted_revision_id: str = "not-the-law-selected-revision",
) -> None:
    """Write a work unit whose stored revision has drifted from the law-selected one.

    ``create_work_unit`` itself re-confirms the law-selected pairing at write
    time, so a genuinely stale stored revision (the registry's law-selected
    pick moved on after the work unit was created under an earlier orden) is
    reproduced here the same way :mod:`test_work_addressing` reproduces a
    generation-superseding write: by constructing the catalogue directly,
    never by asking Workspace to accept a hand-picked mismatch.
    """
    from ....domain.modelos.work_unit import WorkUnitCatalogue, derive_work_unit_id

    payload = work_unit.model_dump()
    payload.update(
        work_unit_id=derive_work_unit_id(
            bucket_id=work_unit.bucket_id,
            modelo=work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period,
            revision_id=corrupted_revision_id,
        ),
        revision_id=corrupted_revision_id,
    )
    repository.save(WorkUnitCatalogue.from_work_units((WorkUnit(**payload),)))


def _exact_target(work_unit: WorkUnit):
    from ..work_addressing import ModeloExactWorkUnitTarget

    return ModeloExactWorkUnitTarget(work_unit_id=work_unit.work_unit_id, bucket_id=work_unit.bucket_id)


def test_visible_target_projects_into_a_selector_request_with_no_exact_operands() -> None:
    """The visible-target mapping must carry natural coordinates, not an exact work-unit lookup."""
    target = _visible_target("some-bucket", revision_id="2019-y-siguientes")

    request = modelo_work_selector_request_for_target(target, bucket_id="some-bucket")

    assert request.modelo == "130"
    assert request.filing_year == 2026
    assert request.revision_id == "2019-y-siguientes"
    assert request.bucket_id == "some-bucket"
    assert request.work_unit_id is None
    assert request.has_visible_target
    assert not request.has_exact_target


def test_formula_operand_references_answer_the_input_direction_not_the_output_direction() -> None:
    """A real revision where the same casilla is both a formula's output and another's input."""
    authority = bundled_authority()
    snapshot = authority.snapshot("130", filing_year=2026, period="1T")
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


def test_relation_source_endpoint_matches_the_registrys_own_source_casilla_field() -> None:
    authority = bundled_authority()
    snapshot = authority.snapshot("303", filing_year=2026, period="1T")
    relations = snapshot.revision.relations
    assert relations  # sanity: this fixture coordinate carries a real relation

    endpoints = relation_source_endpoints_for_casilla(relations, "iva.compensacion-disponible-fin-periodo")

    assert len(endpoints) == 1
    assert endpoints[0].relation_id == "modelo-303-rel-self-compensacion-anteriores"
    assert endpoints[0].casilla_id == "iva.compensacion-disponible-fin-periodo"

    # A different casilla id must never match.
    assert relation_source_endpoints_for_casilla(relations, "not-the-source-casilla") == ()


def test_relation_target_endpoint_matches_the_registrys_own_target_binding_field() -> None:
    authority = bundled_authority()
    snapshot = authority.snapshot("303", filing_year=2026, period="1T")
    relations = snapshot.revision.relations

    endpoints = relation_target_endpoints_for_binding(relations, "modelo-303-compensacion-pendiente-anteriores")

    assert len(endpoints) == 1
    assert endpoints[0].relation_id == "modelo-303-rel-self-compensacion-anteriores"
    assert endpoints[0].binding_id == "modelo-303-compensacion-pendiente-anteriores"

    # The relation's own SOURCE casilla id must never be accepted as a target binding.
    assert relation_target_endpoints_for_binding(relations, "iva.compensacion-disponible-fin-periodo") == ()


def test_static_inspection_schema_identity_is_stable_and_uses_the_s278_manifest_digest() -> None:
    """schema_identity must use the generated-manifest digest, never the completeness manifest's."""
    from ....application.modelo.workspace_manifest import generate_modelo_workspace_field_manifest_for_inspection
    from ....domain.calculations.registry.static_inspection import RegistryRevisionInspection

    authority = bundled_authority()
    capture = authority.capture_law_selected_projection("130", filing_year=2026, period="1T")
    inspection = capture.projection
    assert isinstance(inspection, RegistryRevisionInspection)

    identity = resolve_static_inspection_schema_identity(inspection)
    identity_again = resolve_static_inspection_schema_identity(inspection)

    assert identity == identity_again
    assert identity.schema_id == f"modelo-130-{_LAW_SELECTED_REVISION_ID}"
    assert (
        identity.field_manifest_digest
        == generate_modelo_workspace_field_manifest_for_inspection(inspection).manifest_digest
    )


def test_static_inspection_evidence_horizon_is_stable_and_sourced_from_the_inspection() -> None:
    authority = bundled_authority()
    capture = authority.capture_law_selected_projection("130", filing_year=2026, period="1T")
    inspection = capture.projection
    from ....domain.calculations.registry.static_inspection import RegistryRevisionInspection

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


def _assemble_static_inspection_pieces(bucket_id: str, repository: WorkUnitCatalogueRepository):
    """Build every piece needed for schema_facet tests, real captures throughout."""
    from ....core.external_constants import OutputLanguage
    from ....domain.calculations.registry.static_inspection import RegistryRevisionInspection
    from ..workspace_producers import ModeloWorkspaceFieldManifestPortV1, ModeloWorkspaceLocaleCataloguePortV1

    authority = bundled_authority()
    work_capture, registry_capture, _axes = capture_modelo_workspace_target_captures(
        _visible_target(bucket_id),
        bucket_id=bucket_id,
        catalogue_repository=repository,
        authority=authority,
    )
    registry_projection = registry_capture.projection
    inspection = registry_projection.inspection
    assert isinstance(inspection, RegistryRevisionInspection)

    from ..workspace import resolve_modelo_workspace_revision_axes
    from ..workspace_models import ModeloWorkspaceResolvedTargetV1

    resolution = work_capture.projection
    axes = resolve_modelo_workspace_revision_axes(resolution, registry_projection=registry_projection)
    work_unit = resolution.work_unit
    assert resolution.filing_year is not None
    target = ModeloWorkspaceResolvedTargetV1(
        bucket_id=resolution.bucket_id,
        modelo=resolution.modelo,
        filing_year=resolution.filing_year,
        period=resolution.period,
        law_selected_revision_id=axes.law_selected_revision_id,
        review_status=registry_projection.review_status,
        requested_revision_assertion=axes.requested_revision_assertion,
        stored_revision_assertion=axes.stored_revision_assertion,
        work_unit_id=work_unit.work_unit_id if work_unit is not None else None,
        work_state=work_unit.state if work_unit is not None else None,
    )
    schema_identity = resolve_static_inspection_schema_identity(inspection)
    locale = capture_modelo_workspace_locale_summary(target, output_language=OutputLanguage.ES)
    locale_capture = ModeloWorkspaceLocaleCataloguePortV1(
        translation_key="modelo.schema.130.revision.2019-y-siguientes.field.label",
        locale=OutputLanguage.ES.value,
    ).capture_projection_with_epoch()
    field_manifest_capture = ModeloWorkspaceFieldManifestPortV1(authority=inspection).capture_projection_with_epoch()
    baseline = resolve_static_inspection_baseline(
        target,
        schema_identity=schema_identity,
        locale=locale,
        work_stamp=work_capture.stamp,
        work_epoch=work_capture.epoch,
        registry_stamp=registry_capture.stamp,
        registry_epoch=registry_capture.epoch,
        locale_stamp=locale_capture.stamp,
        locale_epoch=locale_capture.epoch,
        field_manifest_stamp=field_manifest_capture.stamp,
        field_manifest_epoch=field_manifest_capture.epoch,
    )
    contributors = static_inspection_contributors()
    return inspection, target, schema_identity, baseline, contributors


def test_static_inspection_casilla_schema_records_use_the_s277_joins_and_s283_absence() -> None:
    from ....core.external_constants import OutputLanguage

    authority = bundled_authority()
    capture = authority.capture_law_selected_projection("130", filing_year=2026, period="1T")
    from ....domain.calculations.registry.static_inspection import RegistryRevisionInspection

    inspection = capture.projection
    assert isinstance(inspection, RegistryRevisionInspection)

    from ..workspace_models import ModeloWorkspaceResolvedTargetV1, ModeloWorkspaceRevisionAssertionV1

    # A minimal, directly constructed resolved target is legitimate here: this
    # test targets record construction from the inspection, not the capture
    # ordering already proven elsewhere.
    target = ModeloWorkspaceResolvedTargetV1(
        bucket_id="test-bucket-0000-0000-0000-000000000000",
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        law_selected_revision_id=_LAW_SELECTED_REVISION_ID,
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

    from ..workspace_models import ModeloWorkspaceCasillaReferenceV1, ModeloWorkspaceLocalizedTextV1

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
    workspace_repos: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    from ....core.external_constants import OutputLanguage

    bucket_id, repository = workspace_repos
    _seed_work_unit(repository, bucket_id=bucket_id)
    inspection, target, schema_identity, baseline, contributors = _assemble_static_inspection_pieces(
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
    workspace_repos: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    from ....core.external_constants import OutputLanguage

    bucket_id, repository = workspace_repos
    _seed_work_unit(repository, bucket_id=bucket_id)
    inspection, target, schema_identity, baseline, contributors = _assemble_static_inspection_pieces(
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


def _real_303_inspection() -> RegistryRevisionInspection:
    from ....domain.calculations.registry.static_inspection import RegistryRevisionInspection

    authority = bundled_authority()
    capture = authority.capture_law_selected_projection("303", filing_year=2026, period="1T")
    inspection = capture.projection
    assert isinstance(inspection, RegistryRevisionInspection)
    return inspection


def _real_303_snapshot():
    from ....core.authority_grade import RegistryAuthorityGrade
    from ....domain.calculations.registry.schema import RegistrySnapshot

    authority = bundled_authority()
    capture = authority.capture_law_selected_projection(
        "303", filing_year=2026, period="1T", grade=RegistryAuthorityGrade.CALCULATION
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
    inspection = _real_303_inspection()
    snapshot = _real_303_snapshot()
    revision = snapshot.revision

    inspection_bindings = binding_schema_records(inspection.binding_ids, inspection.bindings, inspection.relations)
    snapshot_binding_ids = frozenset(binding.id for binding in revision.bindings)
    snapshot_bindings = binding_schema_records(snapshot_binding_ids, revision.bindings, revision.relations)
    assert inspection_bindings == snapshot_bindings
    assert len(inspection_bindings) > 0

    inspection_formulas = formula_schema_records(inspection.formulas)
    snapshot_formulas = formula_schema_records(revision.formulas)
    assert inspection_formulas == snapshot_formulas
    assert len(inspection_formulas) > 0

    inspection_relations = relation_schema_records(inspection.relations)
    snapshot_relations = relation_schema_records(revision.relations)
    assert inspection_relations == snapshot_relations
    assert len(inspection_relations) > 0

    inspection_parameters = parameter_schema_records(inspection.parameters, inspection.formulas)
    snapshot_parameters = parameter_schema_records(revision.parameters, revision.formulas)
    assert inspection_parameters == snapshot_parameters
    assert len(inspection_parameters) > 0


def test_static_inspection_binding_schema_records_use_the_real_binding_definitions() -> None:
    from ..workspace_models import ModeloWorkspaceBindingReferenceV1, ModeloWorkspaceTechnicalLabelV1

    inspection = _real_303_inspection()
    records = binding_schema_records(inspection.binding_ids, inspection.bindings, inspection.relations)

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

    by_id = dict(zip(binding_ids, records, strict=True))
    target_binding = "modelo-303-compensacion-pendiente-anteriores"
    assert any(
        endpoint.relation_id == "modelo-303-rel-self-compensacion-anteriores"
        for endpoint in by_id[target_binding].relation_endpoints
    )


def test_static_inspection_formula_schema_records_carry_their_own_full_operand_set() -> None:
    from ..workspace_models import ModeloWorkspaceFormulaReferenceV1, ModeloWorkspaceTechnicalLabelV1

    inspection = _real_303_inspection()
    records = formula_schema_records(inspection.formulas)

    assert len(records) == len(inspection.formulas)
    for record in records:
        assert isinstance(record.reference, ModeloWorkspaceFormulaReferenceV1)
        assert isinstance(record.label, ModeloWorkspaceTechnicalLabelV1)
        assert record.label.identifier == record.reference.formula_id
        assert record.legal_refs is not None


def test_static_inspection_relation_schema_records_state_both_of_their_own_endpoints() -> None:
    from ..workspace_models import (
        ModeloWorkspaceRelationReferenceV1,
        ModeloWorkspaceRelationSourceEndpointReferenceV1,
        ModeloWorkspaceRelationTargetEndpointReferenceV1,
    )

    inspection = _real_303_inspection()
    records = relation_schema_records(inspection.relations)

    assert len(records) == len(inspection.relations)
    record = records[0]
    assert isinstance(record.reference, ModeloWorkspaceRelationReferenceV1)
    assert record.reference.relation_id == "modelo-303-rel-self-compensacion-anteriores"
    endpoint_kinds = {type(endpoint) for endpoint in record.relation_endpoints}
    assert endpoint_kinds == {
        ModeloWorkspaceRelationSourceEndpointReferenceV1,
        ModeloWorkspaceRelationTargetEndpointReferenceV1,
    }


def test_static_inspection_parameter_schema_records_key_off_dispatching_formulas() -> None:
    from ..workspace_models import ModeloWorkspaceParameterReferenceV1

    inspection = _real_303_inspection()
    records = parameter_schema_records(inspection.parameters, inspection.formulas)

    assert len(records) == len(inspection.parameters)
    for record in records:
        assert isinstance(record.reference, ModeloWorkspaceParameterReferenceV1)
        assert record.legal_refs is not None


def test_static_inspection_schema_records_covers_all_five_reference_kinds_deterministically() -> None:
    from ....core.external_constants import OutputLanguage

    inspection = _real_303_inspection()
    target = _minimal_resolved_target(inspection)

    records = static_inspection_schema_records(inspection, target, output_language=OutputLanguage.ES)
    records_again = static_inspection_schema_records(inspection, target, output_language=OutputLanguage.ES)

    expected_total = (
        len(inspection.casilla_ids)
        + len(inspection.binding_ids)
        + len(inspection.formulas)
        + len(inspection.relations)
        + len(inspection.parameters)
    )
    assert len(records) == expected_total
    assert records == records_again  # deterministic ordering across identical repeated reads

    kinds = {record.reference.kind for record in records}
    assert kinds == {"casilla", "binding", "formula", "relation", "parameter"}


def _minimal_resolved_target(inspection):
    from ..workspace_models import ModeloWorkspaceResolvedTargetV1, ModeloWorkspaceRevisionAssertionV1

    return ModeloWorkspaceResolvedTargetV1(
        bucket_id="test-bucket-0000-0000-0000-000000000000",
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
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
    inspection = _real_303_inspection()

    dispositions = static_inspection_family_dispositions(inspection)

    assert len(dispositions) == len(inspection.family_dispositions)
    by_family = {d.family: d for d in dispositions}
    assert "applicability" in by_family
    assert by_family["applicability"].disposition == RegistrySchemaFamilyDisposition.NOT_APPLICABLE
    assert by_family["applicability"].legal_refs == inspection.family_dispositions["applicability"].legal_refs
    # A family the inspection has no data for at all (e.g. "constructs") is
    # never reported here -- reporting nothing is honest, guessing is not.
    assert "constructs" not in by_family


def test_a_caller_can_spend_the_cursor_the_schema_facet_mints(
    workspace_repos: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """The public resolver accepts the cursor it mints and returns the NEXT page.

    The paginator could always page; no public entry point could. Both read
    resolvers took ``page_size`` and no cursor, so a facet returned a valid
    ``next_cursor`` that no caller could redeem, and paging is the normal case
    on the provenance destination where one source ref fans out per casilla.

    Re-resolving is not a workaround and is not what this proves: a fresh
    capture invalidates the held cursor by construction, which is the exact
    property the cursor exists to certify. This drives the SAME entry point
    twice, spending page one's cursor on the second call.
    """
    from ....core.external_constants import OutputLanguage

    bucket_id, repository = workspace_repos
    _seed_work_unit(repository, bucket_id=bucket_id)
    authority = bundled_authority()

    def _resolve(cursor=None):
        return resolve_static_inspection_result(
            _visible_target(bucket_id),
            bucket_id=bucket_id,
            catalogue_repository=repository,
            authority=authority,
            output_language=OutputLanguage.ES,
            page_size=5,
            cursor=cursor,
        )

    first = _resolve().projection.schema_facet
    assert first.has_more, "the paging proof needs a schema facet past the page size"
    assert first.next_cursor is not None

    second = _resolve(first.next_cursor).projection.schema_facet

    # The cursor must advance, not restart. Comparing the record identities
    # rather than the counts: a second call that silently returned page one
    # again would match on length and on has_more, and only the contents
    # distinguish "continued" from "started over".
    first_refs = tuple(str(record.reference) for record in first.records)
    second_refs = tuple(str(record.reference) for record in second.records)
    assert second_refs, "spending the cursor returned an empty page"
    assert not set(first_refs) & set(second_refs), "the cursor restarted instead of continuing"


def test_a_cursor_naming_a_facet_the_resolver_does_not_paginate_refuses(
    workspace_repos: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """A cursor for another facet must refuse, never silently return page one.

    Static inspection assembles only the schema facet. Accepting a
    provenance cursor and ignoring it would hand back the first page while
    the caller believed it was continuing, which is the failure the cursor
    exists to make impossible.
    """
    from ....core.external_constants import OutputLanguage
    from ..workspace import ModeloWorkspaceStaleCursorError

    bucket_id, repository = workspace_repos
    _seed_work_unit(repository, bucket_id=bucket_id)
    authority = bundled_authority()

    minted = resolve_static_inspection_result(
        _visible_target(bucket_id),
        bucket_id=bucket_id,
        catalogue_repository=repository,
        authority=authority,
        output_language=OutputLanguage.ES,
        page_size=5,
    ).projection.schema_facet.next_cursor
    assert minted is not None

    foreign = minted.model_copy(update={"facet": ModeloWorkspaceFacetName.PROVENANCE})
    with pytest.raises(ModeloWorkspaceStaleCursorError):
        resolve_static_inspection_result(
            _visible_target(bucket_id),
            bucket_id=bucket_id,
            catalogue_repository=repository,
            authority=authority,
            output_language=OutputLanguage.ES,
            page_size=5,
            cursor=foreign,
        )


def test_resolve_static_inspection_result_assembles_a_complete_valid_projection(
    workspace_repos: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    from ....core.external_constants import OutputLanguage

    bucket_id, repository = workspace_repos
    _seed_work_unit(repository, bucket_id=bucket_id)
    authority = bundled_authority()

    result = resolve_static_inspection_result(
        _visible_target(bucket_id),
        bucket_id=bucket_id,
        catalogue_repository=repository,
        authority=authority,
        output_language=OutputLanguage.ES,
    )

    projection = result.projection
    assert projection.target.modelo == "130"
    assert projection.target.law_selected_revision_id == _LAW_SELECTED_REVISION_ID
    assert projection.schema_facet.records  # a real, non-empty schema facet
    assert projection.work_review is STATIC_INSPECTION_WORK_REVIEW_FACET
    assert len(projection.capabilities) == len(ModeloWorkspaceCapabilityName)
    assert projection.materialization_facet is None
    assert projection.provenance_facet is None

    # Round-trip through JSON must reproduce the identical result.
    from ..workspace_models import ModeloWorkspaceStaticInspectionResultV1

    reloaded = ModeloWorkspaceStaticInspectionResultV1.model_validate_json(result.model_dump_json())
    assert reloaded == result


def test_resolve_static_inspection_result_never_re_reads_the_work_catalogue(
    workspace_repos: tuple[str, WorkUnitCatalogueRepository],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A single encrypted-SQL work-catalogue read must back the entire assembled result."""
    import logging

    bucket_id, repository = workspace_repos
    _seed_work_unit(repository, bucket_id=bucket_id)
    authority = bundled_authority()

    from ....core.external_constants import OutputLanguage

    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger="cadrumo.adapters.persistence.profile.modelos_work_units"):
        result = resolve_static_inspection_result(
            _visible_target(bucket_id),
            bucket_id=bucket_id,
            catalogue_repository=repository,
            authority=authority,
            output_language=OutputLanguage.ES,
        )

    assert result.projection.target.modelo == "130"
    load_log_lines = [record for record in caplog.records if "loaded work-unit catalogue" in record.message]
    assert len(load_log_lines) == 1


def test_capture_with_a_grade_admits_a_registry_snapshot_reading_work_and_registry_exactly_once(
    workspace_repos: tuple[str, WorkUnitCatalogueRepository],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Capture core: passing a grade switches REGISTRY's admission, not the read count or ordering."""
    import logging

    from ....core.authority_grade import RegistryAuthorityGrade
    from ....domain.calculations.registry.schema import RegistrySnapshot

    bucket_id, repository = workspace_repos
    _seed_work_unit(repository, bucket_id=bucket_id)
    authority = bundled_authority()

    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger="cadrumo.adapters.persistence.profile.modelos_work_units"):
        work_capture, registry_capture, axes = capture_modelo_workspace_target_captures(
            _visible_target(bucket_id),
            bucket_id=bucket_id,
            catalogue_repository=repository,
            authority=authority,
            grade=RegistryAuthorityGrade.CALCULATION,
        )

    assert work_capture.projection.work_unit is not None
    assert registry_capture.projection.snapshot is not None
    assert isinstance(registry_capture.projection.snapshot, RegistrySnapshot)
    assert registry_capture.projection.inspection is None
    assert axes.law_selected_revision_id == _LAW_SELECTED_REVISION_ID

    load_log_lines = [record for record in caplog.records if "loaded work-unit catalogue" in record.message]
    assert len(load_log_lines) == 1


def _real_calculation_revision_with_row_materialization():
    """Build a real CalculationRevision carrying both a scalar and a repeated row.

    Mirrors the construction pattern in
    ``test_source_mesh_revision_roundtrip.py`` -- the only existing site that
    builds one of these with row materialization, confirming this shape is
    the real one rather than an invented fixture.
    """
    from decimal import Decimal

    from ....core.casilla_id import validated_casilla_id
    from ....domain.calculations.registry.bindings import CasillaObservation
    from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
    from ....domain.calculations.row_casilla import DirectRowMaterializationProvenance
    from ....domain.calculations.row_source_identity import RowSourceIdentity
    from ....domain.modelos.calculation_revision import (
        CalculationRevision,
        CalculationRevisionState,
        derive_calculation_revision_id,
    )
    from ....domain.modelos.work_unit import derive_work_unit_id

    bucket_id = "30330300-0000-4000-8000-000000000601"
    scalar_casilla = validated_casilla_id("00501")
    row_casilla = validated_casilla_id("00181")
    now = datetime(2026, 7, 4, 14, 0, tzinfo=UTC)

    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2022",
    )
    row_identity = RowSourceIdentity(
        source_kind=BindingSourceKind.INVENTORY,
        source_row_identity="materialization-facet-canary",
        fingerprint="7" * 64,
    )
    row_binding_values = {"inventory-operation-0181": {"1": "120.00"}}
    row_source_identities = {("inventory-operation-0181", 1): row_identity}
    row_casilla_values = {(row_casilla, 1): Decimal("120.00")}
    row_casilla_provenance = {
        (row_casilla, 1): DirectRowMaterializationProvenance(
            source_binding_id="inventory-operation-0181",
            source_row_index=1,
            source_identity=row_identity,
            materialization_rule_id="inventory-operation-0181",
            materialization_rule_version="2022",
        )
    }
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={scalar_casilla: "140000.00"},
        binding_overrides={},
        row_binding_values=row_binding_values,
        row_source_identities=row_source_identities,
        row_casilla_values=row_casilla_values,
        row_casilla_provenance=row_casilla_provenance,
        casilla_values={scalar_casilla: Decimal("140000.00")},
        source_provenance=(),
        filing_instance_evidence=None,
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo="303",
            revision_id="2022",
            modelo_year=2026,
            period="1T",
        ),
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={scalar_casilla: "140000.00"},
        row_binding_values=row_binding_values,
        row_source_identities=row_source_identities,
        row_casilla_values=row_casilla_values,
        row_casilla_provenance=row_casilla_provenance,
        casilla_values={scalar_casilla: Decimal("140000.00")},
        observations=(
            CasillaObservation(
                casilla_id=scalar_casilla,
                value=Decimal("140000.00"),
                legal_refs=("ley-37-1992:art-99",),
                source_refs=("boe-modelo-303-2025-form",),
            ),
        ),
        source_provenance=(),
        created_at=now,
        updated_at=now,
        filing_instance_evidence=None,
    )


def _production_default_page_size() -> int:
    """Return a bounded page size for paginator-focused test fixtures."""
    return 200


def _real_303_casilla_ids() -> tuple[str, ...]:
    """Return every casilla id the bundled M303 2026/1T revision declares.

    The bundled registry drives the count: this revision declares more
    casillas than the graded assembly's own page size, which is what makes
    it the honest anchor for a paging proof. The overflow is the shipped
    registry's shape, not a number these tests chose.
    """
    return tuple(_real_303_inspection().casilla_ids)


def _paging_coordinate(bucket_id: str, repository: WorkUnitCatalogueRepository):
    """Return the (target, schema_identity, baseline, contributors) paging pins.

    Reuses the real-capture static assembly because the paginator is
    admission-agnostic: it pins a baseline coordinate and mints a cursor
    against it, and never inspects which admission produced that baseline.
    Admission-versus-facet coherence is :class:`ModeloWorkspaceProjectionV1`'s
    invariant, proven separately, not this helper's.
    """
    _inspection, target, schema_identity, baseline, contributors = _assemble_static_inspection_pieces(
        bucket_id, repository
    )
    return target, schema_identity, baseline, contributors


def _drain_pages(facet_type, records, *, facet, target, schema_identity, baseline, contributors, page_size):
    """Page the whole sequence through the real paginator, returning every page."""
    pages = []
    cursor = None
    while True:
        page = paginate_modelo_workspace_facet(
            facet_type,
            records,
            facet=facet,
            target=target,
            schema_identity=schema_identity,
            baseline=baseline,
            contributors=contributors,
            disposition=ModeloWorkspaceCapabilityDisposition.AVAILABLE,
            page_size=page_size,
            cursor=cursor,
        )
        pages.append(page)
        if page.next_cursor is None:
            return tuple(pages)
        cursor = page.next_cursor


def test_materialization_facet_pages_a_real_revision_that_exceeds_the_page_size(
    workspace_repos: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """A real M303 revision overflows one page and paginates instead of refusing.

    Before the shared paginator, the graded assembly truncated to
    ``page_size`` and set ``has_more`` without minting the matching cursor,
    so ``ModeloWorkspaceBoundedFacetV1`` refused the facet outright and took
    the whole projection down. This modelo's own casilla set is past the
    page size, so the failure was reachable with shipped registry data.
    """
    from decimal import Decimal

    from ....core.casilla_id import validated_casilla_id

    bucket_id, repository = workspace_repos
    _seed_work_unit(repository, bucket_id=bucket_id)
    target, schema_identity, baseline, contributors = _paging_coordinate(bucket_id, repository)
    page_size = _production_default_page_size()

    casilla_ids = _real_303_casilla_ids()
    assert len(casilla_ids) > page_size, "the paging proof needs a real revision past the production page size"

    records = tuple(
        ModeloWorkspaceScalarMaterializationRecordV1(
            scalar=ModeloWorkspaceScalarMaterializationV1(
                casilla_id=validated_casilla_id(casilla_id), value=Decimal("1.00")
            )
        )
        for casilla_id in casilla_ids
    )

    pages = _drain_pages(
        ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceMaterializationRecordV1],
        records,
        facet=ModeloWorkspaceFacetName.MATERIALIZATION,
        target=target,
        schema_identity=schema_identity,
        baseline=baseline,
        contributors=contributors,
        page_size=page_size,
    )

    assert len(pages) > 1
    assert pages[0].has_more is True
    assert pages[0].next_cursor is not None
    assert pages[0].next_cursor.facet is ModeloWorkspaceFacetName.MATERIALIZATION
    assert len(pages[0].records) == page_size
    assert pages[-1].has_more is False
    assert pages[-1].next_cursor is None
    collected = tuple(record for page in pages for record in page.records)
    assert collected == records


def test_an_overflowing_facet_built_without_a_cursor_still_refuses(
    workspace_repos: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """Anti-tautology: the invariant the paginator satisfies still bites when violated.

    Two proofs, so the paging tests above cannot pass vacuously. First the
    pre-fix construction shape -- truncate to ``page_size``, declare
    ``has_more``, mint no cursor -- is rejected, which is exactly the live
    defect and shows those tests target something real. Second a genuine
    paginated page has its cursor stripped and is rejected too, so the
    agreement is enforced on the model rather than merely produced by the
    helper.
    """
    from decimal import Decimal

    from pydantic import ValidationError

    from ....core.casilla_id import validated_casilla_id

    bucket_id, repository = workspace_repos
    _seed_work_unit(repository, bucket_id=bucket_id)
    target, schema_identity, baseline, contributors = _paging_coordinate(bucket_id, repository)
    page_size = _production_default_page_size()

    records = tuple(
        ModeloWorkspaceScalarMaterializationRecordV1(
            scalar=ModeloWorkspaceScalarMaterializationV1(
                casilla_id=validated_casilla_id(casilla_id), value=Decimal("1.00")
            )
        )
        for casilla_id in _real_303_casilla_ids()
    )
    assert len(records) > page_size

    with pytest.raises(ValidationError, match="has_more must agree with next_cursor"):
        ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceMaterializationRecordV1](
            selected_revision_id=target.law_selected_revision_id,
            schema_identity=schema_identity,
            baseline=baseline,
            contributor_epoch_digest=baseline.contributor_epoch_digest,
            contributors=contributors,
            facet=ModeloWorkspaceFacetName.MATERIALIZATION,
            disposition=ModeloWorkspaceCapabilityDisposition.AVAILABLE,
            records=records[:page_size],
            page_size=page_size,
            has_more=len(records) > page_size,
        )

    page = paginate_modelo_workspace_facet(
        ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceMaterializationRecordV1],
        records,
        facet=ModeloWorkspaceFacetName.MATERIALIZATION,
        target=target,
        schema_identity=schema_identity,
        baseline=baseline,
        contributors=contributors,
        disposition=ModeloWorkspaceCapabilityDisposition.AVAILABLE,
        page_size=page_size,
    )
    assert page.next_cursor is not None
    with pytest.raises(ValidationError, match="has_more must agree with next_cursor"):
        ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceMaterializationRecordV1].model_validate(
            {**page.model_dump(), "next_cursor": None}
        )


def _resolved_target_with_work_unit(*, work_unit_id: str, revision_id: str = "2022"):
    from ....core.revision_review import RevisionReviewStatus
    from ....domain.modelos.work_unit import WorkUnitState
    from ..workspace_models import (
        ModeloWorkspaceResolvedTargetV1,
        ModeloWorkspaceRevisionAssertionV1,
    )

    return ModeloWorkspaceResolvedTargetV1(
        bucket_id="test-bucket-0000-0000-0000-000000000000",
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        law_selected_revision_id=revision_id,
        review_status=RevisionReviewStatus.PENDING_REVIEW,
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
        work_unit_id=work_unit_id,
        work_state=WorkUnitState.BORRADOR,
    )


def _minimal_calculation_revision(*, work_unit_id: str, state):
    from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
    from ....domain.modelos.calculation_revision import (
        CalculationRevision,
        CalculationRevisionState,
        derive_calculation_revision_id,
    )

    now = datetime(2026, 7, 4, 14, 0, tzinfo=UTC)
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        source_provenance=(),
        filing_instance_evidence=None,
    )
    verified_at = now if state is CalculationRevisionState.VERIFICADO_COMPLETO else None
    verified_by = "test-operator" if state is CalculationRevisionState.VERIFICADO_COMPLETO else None
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo="303",
            revision_id="2022",
            modelo_year=2026,
            period="1T",
        ),
        state=state,
        casilla_values={},
        observations=(),
        source_provenance=(),
        created_at=now,
        updated_at=now,
        filing_instance_evidence=None,
        verified_at=verified_at,
        verified_by=verified_by,
    )
