"""Integration contracts for the Workspace V1 WORK-then-REGISTRY capture core."""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import BindingSourceKind, Period, RegistrySchemaFamilyDisposition
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.modelos import WorkUnit
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.secure_sql import isolated_runtime_profile
from ...registry.source_connectivity import load_source_connectivity_census
from .._work_lifecycle import create_work_unit
from ..work_addressing import ModeloWorkRegistryYearMismatchError
from ..workspace import (
    STATIC_INSPECTION_WORK_REVIEW_FACET,
    ModeloWorkspaceStaleCursorError,
    binding_schema_records,
    capture_modelo_workspace_locale_summary,
    capture_modelo_workspace_target_axes,
    capture_modelo_workspace_target_captures,
    formula_operand_references_for_casilla,
    formula_schema_records,
    graded_snapshot_casilla_schema_records,
    graded_snapshot_materialization_facet,
    graded_snapshot_modelo_workspace_capabilities,
    graded_snapshot_provenance_facet,
    graded_snapshot_readiness,
    modelo_work_selector_request_for_target,
    paginate_static_inspection_schema_facet,
    parameter_schema_records,
    relation_schema_records,
    relation_source_endpoints_for_casilla,
    relation_target_endpoints_for_binding,
    resolve_modelo_workspace_target,
    resolve_static_inspection_baseline,
    resolve_static_inspection_result,
    resolve_static_inspection_schema_identity,
    static_inspection_casilla_schema_records,
    static_inspection_contributors,
    static_inspection_evidence_horizon,
    static_inspection_family_dispositions,
    static_inspection_modelo_workspace_capabilities,
    static_inspection_schema_records,
)
from ..workspace_models import (
    ModeloVisibleFilingTarget,
    ModeloWorkspaceCapabilityDisposition,
    ModeloWorkspaceCapabilityName,
    ModeloWorkspaceExactWorkUnitTargetV1,
    ModeloWorkspaceLocaleDisposition,
    ModeloWorkspaceRevisionAssertionDisposition,
    ModeloWorkspaceRevisionAssertionSource,
    ModeloWorkspaceVisibleFilingTargetV1,
)
from ..workspace_producers import ModeloWorkspaceRegistryProjectionV1

#: Fixed observation instant for the closure capture, so a limb set does not
#: shift under the suite because a census entry expired between runs.
_CLOSURE_AS_OF = date(2026, 8, 24)

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


def test_capture_resolves_registry_from_the_captured_work_coordinate_not_the_target(
    workspace_repos: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """REGISTRY must be captured from resolution.modelo/filing_year/period, never target operands."""
    bucket_id, repository = workspace_repos
    _seed_work_unit(repository, bucket_id=bucket_id)
    authority = bundled_authority()

    resolution, registry_projection, axes = capture_modelo_workspace_target_axes(
        _visible_target(bucket_id),
        bucket_id=bucket_id,
        catalogue_repository=repository,
        authority=authority,
    )

    assert resolution.work_unit is not None
    assert isinstance(registry_projection, ModeloWorkspaceRegistryProjectionV1)
    assert registry_projection.inspection is not None
    assert registry_projection.revision_id == _LAW_SELECTED_REVISION_ID
    assert axes.law_selected_revision_id == _LAW_SELECTED_REVISION_ID
    assert axes.requested_revision_assertion.disposition == ModeloWorkspaceRevisionAssertionDisposition.NOT_PRESENT
    assert axes.stored_revision_assertion.disposition == ModeloWorkspaceRevisionAssertionDisposition.MATCHED
    assert axes.stored_revision_assertion.asserted_revision_id == _LAW_SELECTED_REVISION_ID


def test_requested_and_stored_axes_are_judged_independently_against_the_same_capture(
    workspace_repos: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """A matching requested revision must not be conflated with the stored axis, or vice versa."""
    bucket_id, repository = workspace_repos
    _seed_work_unit(repository, bucket_id=bucket_id)
    authority = bundled_authority()

    _resolution, _projection, axes = capture_modelo_workspace_target_axes(
        _visible_target(bucket_id, revision_id=_LAW_SELECTED_REVISION_ID),
        bucket_id=bucket_id,
        catalogue_repository=repository,
        authority=authority,
    )

    assert axes.requested_revision_assertion.source == ModeloWorkspaceRevisionAssertionSource.REQUESTED
    assert axes.requested_revision_assertion.disposition == ModeloWorkspaceRevisionAssertionDisposition.MATCHED
    assert axes.stored_revision_assertion.source == ModeloWorkspaceRevisionAssertionSource.STORED
    assert axes.stored_revision_assertion.disposition == ModeloWorkspaceRevisionAssertionDisposition.MATCHED


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
    from ....domain.modelos import WorkUnitCatalogue, derive_work_unit_id

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


def test_a_stored_revision_diverging_from_the_law_selected_one_is_typed_data_not_an_exception(
    workspace_repos: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """A mismatch must surface as a MISMATCHED disposition, never an exception that erases it.

    ``ModeloWorkspaceRevisionMismatchRefusalV1`` is built FROM the mismatched
    axes; an exception escaping the axis computation would destroy the exact
    information that typed refusal exists to carry.
    """
    bucket_id, repository = workspace_repos
    work_unit = _seed_work_unit(repository, bucket_id=bucket_id)
    _corrupt_stored_revision(repository, work_unit)
    authority = bundled_authority()

    resolution, _projection, axes = capture_modelo_workspace_target_axes(
        _visible_target(bucket_id),
        bucket_id=bucket_id,
        catalogue_repository=repository,
        authority=authority,
    )

    assert resolution.work_unit is not None
    assert axes.stored_revision_assertion.disposition == ModeloWorkspaceRevisionAssertionDisposition.MISMATCHED
    assert axes.stored_revision_assertion.asserted_revision_id == "not-the-law-selected-revision"
    assert axes.requested_revision_assertion.disposition == ModeloWorkspaceRevisionAssertionDisposition.NOT_PRESENT
    assert axes.law_selected_revision_id == _LAW_SELECTED_REVISION_ID


def test_the_pure_assertion_still_raises_for_a_caller_that_wants_a_hard_refusal(
    workspace_repos: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """The sole pure assertion this module reuses for text still raises on the same mismatch."""
    from ....domain.calculations.registry.authority import RegistryAuthorityCapture
    from ..work_addressing import assert_work_target_revision

    bucket_id, repository = workspace_repos
    work_unit = _seed_work_unit(repository, bucket_id=bucket_id)
    _corrupt_stored_revision(repository, work_unit)
    authority = bundled_authority()

    _resolution, projection, _axes = capture_modelo_workspace_target_axes(
        _visible_target(bucket_id),
        bucket_id=bucket_id,
        catalogue_repository=repository,
        authority=authority,
    )
    assert projection.inspection is not None

    with pytest.raises(ModeloWorkRegistryYearMismatchError):
        assert_work_target_revision(
            RegistryAuthorityCapture(projection=projection.inspection, comparison_domain="x", generation=1),
            requested_revision_id=None,
            stored_revision_id="not-the-law-selected-revision",
        )


def test_exact_work_unit_target_derives_registry_coordinates_from_the_resolved_work_unit(
    workspace_repos: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """An exact work-unit target carries no natural coordinates of its own; WORK must supply them."""
    bucket_id, repository = workspace_repos
    work_unit = _seed_work_unit(repository, bucket_id=bucket_id)
    authority = bundled_authority()

    target = ModeloWorkspaceExactWorkUnitTargetV1(target=_exact_target(work_unit))

    resolution, registry_projection, axes = capture_modelo_workspace_target_axes(
        target,
        bucket_id=bucket_id,
        catalogue_repository=repository,
        authority=authority,
    )

    assert resolution.modelo == "130"
    assert registry_projection.revision_id == _LAW_SELECTED_REVISION_ID
    assert axes.stored_revision_assertion.disposition == ModeloWorkspaceRevisionAssertionDisposition.MATCHED


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


def test_resolve_modelo_workspace_target_carries_review_status_from_the_registry_capture(
    workspace_repos: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """The shared resolved-target record must source review_status from the one REGISTRY capture."""
    from ....core import RevisionReviewStatus

    bucket_id, repository = workspace_repos
    work_unit = _seed_work_unit(repository, bucket_id=bucket_id)
    authority = bundled_authority()

    resolved = resolve_modelo_workspace_target(
        _visible_target(bucket_id),
        bucket_id=bucket_id,
        catalogue_repository=repository,
        authority=authority,
    )

    assert resolved.bucket_id == bucket_id
    assert resolved.modelo == "130"
    assert resolved.law_selected_revision_id == _LAW_SELECTED_REVISION_ID
    assert isinstance(resolved.review_status, RevisionReviewStatus)
    assert resolved.work_unit_id == work_unit.work_unit_id
    assert resolved.work_state == work_unit.state
    assert resolved.requested_revision_assertion.source == ModeloWorkspaceRevisionAssertionSource.REQUESTED
    assert resolved.stored_revision_assertion.source == ModeloWorkspaceRevisionAssertionSource.STORED


def test_resolve_modelo_workspace_target_carries_a_mismatched_stored_assertion_without_raising(
    workspace_repos: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """resolve_modelo_workspace_target must never raise for a revision mismatch; it is typed data."""
    bucket_id, repository = workspace_repos
    work_unit = _seed_work_unit(repository, bucket_id=bucket_id)
    _corrupt_stored_revision(repository, work_unit)
    authority = bundled_authority()

    resolved = resolve_modelo_workspace_target(
        _visible_target(bucket_id),
        bucket_id=bucket_id,
        catalogue_repository=repository,
        authority=authority,
    )

    assert resolved.stored_revision_assertion.disposition == ModeloWorkspaceRevisionAssertionDisposition.MISMATCHED
    assert resolved.law_selected_revision_id == _LAW_SELECTED_REVISION_ID


def test_resolve_modelo_workspace_target_carries_no_work_unit_for_an_absent_target(
    workspace_repos: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """An ABSENT resolution must resolve REGISTRY from the request's own coordinates and carry no work unit."""
    bucket_id, repository = workspace_repos
    authority = bundled_authority()

    resolved = resolve_modelo_workspace_target(
        _visible_target(bucket_id),
        bucket_id=bucket_id,
        catalogue_repository=repository,
        authority=authority,
    )

    assert resolved.work_unit_id is None
    assert resolved.work_state is None
    assert resolved.stored_revision_assertion.disposition == ModeloWorkspaceRevisionAssertionDisposition.NOT_PRESENT
    assert resolved.law_selected_revision_id == _LAW_SELECTED_REVISION_ID


def test_locale_summary_resolves_exact_for_a_real_authored_key(
    workspace_repos: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """modelo 130 / 2019-y-siguientes carries a real, non-null Spanish label."""
    from ....core import OutputLanguage

    bucket_id, repository = workspace_repos
    authority = bundled_authority()
    resolved = resolve_modelo_workspace_target(
        _visible_target(bucket_id),
        bucket_id=bucket_id,
        catalogue_repository=repository,
        authority=authority,
    )

    summary = capture_modelo_workspace_locale_summary(resolved, output_language=OutputLanguage.ES)

    assert summary.requested_language == OutputLanguage.ES
    assert summary.resolved_language == OutputLanguage.ES
    assert summary.disposition == ModeloWorkspaceLocaleDisposition.EXACT
    assert len(summary.catalogue_digest) > 0


def test_locale_summary_falls_back_to_spanish_when_the_requested_language_has_no_authored_value(
    workspace_repos: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """modelo 130 / 2019-y-siguientes has a null (untranslated) English revision label."""
    from ....core import OutputLanguage

    bucket_id, repository = workspace_repos
    authority = bundled_authority()
    resolved = resolve_modelo_workspace_target(
        _visible_target(bucket_id),
        bucket_id=bucket_id,
        catalogue_repository=repository,
        authority=authority,
    )

    summary = capture_modelo_workspace_locale_summary(resolved, output_language=OutputLanguage.EN)

    assert summary.requested_language == OutputLanguage.EN
    assert summary.resolved_language == OutputLanguage.ES
    assert summary.disposition == ModeloWorkspaceLocaleDisposition.SPANISH_FALLBACK


def test_static_inspection_capabilities_cover_the_closed_denominator_exactly_once(
    workspace_repos: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """schema_inspection is AVAILABLE (S278); the other four are UNMEASURED (S279), each citing its own producer."""
    bucket_id, repository = workspace_repos
    authority = bundled_authority()
    resolved = resolve_modelo_workspace_target(
        _visible_target(bucket_id),
        bucket_id=bucket_id,
        catalogue_repository=repository,
        authority=authority,
    )

    capabilities = static_inspection_modelo_workspace_capabilities(resolved)

    by_name = {row.capability: row for row in capabilities}
    assert set(by_name) == set(ModeloWorkspaceCapabilityName)
    assert by_name[ModeloWorkspaceCapabilityName.SCHEMA_INSPECTION].disposition == (
        ModeloWorkspaceCapabilityDisposition.AVAILABLE
    )
    for capability_name in (
        ModeloWorkspaceCapabilityName.CALCULATION_MATERIALIZATION,
        ModeloWorkspaceCapabilityName.VERIFICATION_READINESS,
        ModeloWorkspaceCapabilityName.FILING_DRAFT_READINESS,
        ModeloWorkspaceCapabilityName.FILING_EXPORT_READINESS,
    ):
        assert by_name[capability_name].disposition == ModeloWorkspaceCapabilityDisposition.UNMEASURED
    for row in capabilities:
        assert row.selected_revision_id == resolved.law_selected_revision_id
        assert row.target == resolved
    expected_producers = {
        ModeloWorkspaceCapabilityName.SCHEMA_INSPECTION: "workspace_field_manifest",
        ModeloWorkspaceCapabilityName.CALCULATION_MATERIALIZATION: "calculation_materialization",
        ModeloWorkspaceCapabilityName.VERIFICATION_READINESS: "modelo_work_review",
        ModeloWorkspaceCapabilityName.FILING_DRAFT_READINESS: "modelo_readiness",
        ModeloWorkspaceCapabilityName.FILING_EXPORT_READINESS: "registry_closure",
    }
    for capability_name, expected_producer in expected_producers.items():
        assert by_name[capability_name].producer == expected_producer


def test_static_inspection_capabilities_are_identical_regardless_of_work_state(
    workspace_repos: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """Capability dispositions must not be inferred from work_state, review_status or any neighbour.

    Proves S279's rule directly: the same STATIC_INSPECTION capability
    dispositions and producers are returned whether or not a work unit
    exists, and whether the requested-axis assertion is present or absent --
    none of those neighbouring facts may leak into a capability disposition
    that is supposed to be copied from its own canonical producer alone.
    """
    bucket_id, repository = workspace_repos
    authority = bundled_authority()

    absent_target = resolve_modelo_workspace_target(
        _visible_target(bucket_id),
        bucket_id=bucket_id,
        catalogue_repository=repository,
        authority=authority,
    )
    _seed_work_unit(repository, bucket_id=bucket_id)
    present_target = resolve_modelo_workspace_target(
        _visible_target(bucket_id, revision_id=_LAW_SELECTED_REVISION_ID),
        bucket_id=bucket_id,
        catalogue_repository=repository,
        authority=authority,
    )

    assert absent_target.work_unit_id is None
    assert present_target.work_unit_id is not None
    assert (
        present_target.requested_revision_assertion.disposition == ModeloWorkspaceRevisionAssertionDisposition.MATCHED
    )

    absent_capabilities = static_inspection_modelo_workspace_capabilities(absent_target)
    present_capabilities = static_inspection_modelo_workspace_capabilities(present_target)

    absent_shape = {(row.capability, row.disposition, row.producer) for row in absent_capabilities}
    present_shape = {(row.capability, row.disposition, row.producer) for row in present_capabilities}
    assert absent_shape == present_shape


# --- S277: schema-record join semantics, proven against real revisions
# carrying both edge directions ---


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
    """schema_identity must use the S278 generated-manifest digest, never the completeness manifest's."""
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


def test_static_inspection_baseline_pins_the_exact_target_and_revision(
    workspace_repos: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    from ....core import OutputLanguage

    bucket_id, repository = workspace_repos
    _seed_work_unit(repository, bucket_id=bucket_id)
    authority = bundled_authority()

    work_capture, registry_capture, _axes = capture_modelo_workspace_target_captures(
        _visible_target(bucket_id),
        bucket_id=bucket_id,
        catalogue_repository=repository,
        authority=authority,
    )
    resolution = work_capture.projection
    registry_projection = registry_capture.projection
    assert resolution.work_unit is not None
    assert resolution.modelo is not None
    assert resolution.filing_year is not None
    assert resolution.period is not None

    target = resolve_modelo_workspace_target(
        _visible_target(bucket_id),
        bucket_id=bucket_id,
        catalogue_repository=repository,
        authority=authority,
    )
    inspection = registry_projection.inspection
    assert inspection is not None
    schema_identity = resolve_static_inspection_schema_identity(inspection)
    locale = capture_modelo_workspace_locale_summary(target, output_language=OutputLanguage.ES)

    from ....domain.calculations.registry.modelo_localization import revision_locale_key
    from ..workspace_producers import ModeloWorkspaceLocaleCataloguePortV1

    locale_capture = ModeloWorkspaceLocaleCataloguePortV1(
        translation_key=revision_locale_key(target.modelo, target.law_selected_revision_id),
        locale=OutputLanguage.ES.value,
    ).capture_projection_with_epoch()
    field_manifest_capture = None
    from ..workspace_producers import ModeloWorkspaceFieldManifestPortV1

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

    assert baseline.target == target
    assert baseline.selected_revision_id == target.law_selected_revision_id
    assert baseline.schema_identity == schema_identity
    assert baseline.locale_catalogue_digest == locale.catalogue_digest
    assert len(baseline.token) > 0
    assert len(baseline.contributor_stamp_digest) > 0
    assert len(baseline.contributor_epoch_digest) > 0


def _assemble_static_inspection_pieces(bucket_id: str, repository: WorkUnitCatalogueRepository):
    """Build every piece needed for schema_facet tests, real captures throughout."""
    from ....core import OutputLanguage
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

    target = resolve_modelo_workspace_target(
        _visible_target(bucket_id),
        bucket_id=bucket_id,
        catalogue_repository=repository,
        authority=authority,
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
    from ....core import OutputLanguage

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
    from ....core import OutputLanguage

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
        page = paginate_static_inspection_schema_facet(
            records,
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
    from ....core import OutputLanguage

    bucket_id, repository = workspace_repos
    _seed_work_unit(repository, bucket_id=bucket_id)
    inspection, target, schema_identity, baseline, contributors = _assemble_static_inspection_pieces(
        bucket_id, repository
    )
    records = static_inspection_casilla_schema_records(inspection, target, output_language=OutputLanguage.ES)

    first_page = paginate_static_inspection_schema_facet(
        records,
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
        paginate_static_inspection_schema_facet(
            records,
            target=target,
            schema_identity=schema_identity,
            baseline=moved_baseline,
            contributors=contributors,
            disposition=ModeloWorkspaceCapabilityDisposition.AVAILABLE,
            page_size=3,
            cursor=first_page.next_cursor,
        )


def _real_303_inspection():
    from ....domain.calculations.registry.static_inspection import RegistryRevisionInspection

    authority = bundled_authority()
    capture = authority.capture_law_selected_projection("303", filing_year=2026, period="1T")
    inspection = capture.projection
    assert isinstance(inspection, RegistryRevisionInspection)
    return inspection


def _real_303_snapshot():
    from ....core import RegistryAuthorityGrade
    from ....domain.calculations.registry.schema import RegistrySnapshot

    authority = bundled_authority()
    capture = authority.capture_law_selected_projection(
        "303", filing_year=2026, period="1T", grade=RegistryAuthorityGrade.CALCULATION
    )
    snapshot = capture.projection
    assert isinstance(snapshot, RegistrySnapshot)
    return snapshot


def test_shared_schema_record_builders_are_identical_whether_fed_inspection_or_snapshot() -> None:
    """S296: the shared BINDING/FORMULA/RELATION/PARAMETER builders cannot drift between admissions.

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


def test_graded_casilla_schema_records_populate_what_static_correctly_leaves_absent() -> None:
    """S296: the same casilla's legal_refs/constraints are None for static, real for graded."""
    from ....core import OutputLanguage

    inspection = _real_303_inspection()
    snapshot = _real_303_snapshot()
    revision = snapshot.revision

    target = _minimal_resolved_target(inspection)
    static_records = static_inspection_casilla_schema_records(inspection, target, output_language=OutputLanguage.ES)
    graded_records = graded_snapshot_casilla_schema_records(
        revision.casillas, revision.formulas, revision.relations, target, output_language=OutputLanguage.ES
    )

    assert len(graded_records) == len(revision.casillas)
    assert all(record.legal_refs is None for record in static_records)
    assert all(record.constraints is None for record in static_records)
    assert all(record.legal_refs is not None for record in graded_records)
    assert all(record.constraints is not None for record in graded_records)

    # At least one real casilla in this revision declares a non-empty constraints block.
    assert any(record.constraints for record in graded_records)


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
        assert record.legal_refs is not None  # DataBindingDefinition is retained whole
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
    from ....core import OutputLanguage

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


def test_resolve_static_inspection_result_assembles_a_complete_valid_projection(
    workspace_repos: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    from ....core import OutputLanguage

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

    from ....core import OutputLanguage

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
    """S296 capture core: passing a grade switches REGISTRY's admission, not the read count or ordering."""
    import logging

    from ....core import RegistryAuthorityGrade
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

    from ....core import BindingSourceKind, validated_casilla_id
    from ....domain.calculations import DirectRowMaterializationProvenance, RowSourceIdentity
    from ....domain.calculations.registry.bindings import CasillaObservation
    from ....domain.modelos import (
        CalculationRevision,
        CalculationRevisionState,
        derive_calculation_revision_id,
        derive_work_unit_id,
    )

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


def test_graded_snapshot_materialization_facet_covers_scalar_and_repeated_rows() -> None:
    from decimal import Decimal

    from ..workspace_models import (
        ModeloWorkspaceRepeatedRowMaterializationRecordV1,
        ModeloWorkspaceScalarMaterializationRecordV1,
    )

    revision = _real_calculation_revision_with_row_materialization()

    records = graded_snapshot_materialization_facet(revision)

    scalar_records = [r for r in records if isinstance(r, ModeloWorkspaceScalarMaterializationRecordV1)]
    repeated_records = [r for r in records if isinstance(r, ModeloWorkspaceRepeatedRowMaterializationRecordV1)]
    assert len(scalar_records) == 1
    assert scalar_records[0].scalar.value == Decimal("140000.00")
    assert len(repeated_records) == 1
    repeated = repeated_records[0].repeated_row
    assert repeated.binding_id == "inventory-operation-0181"
    assert repeated.row_index == 1
    assert repeated.values[0].value == Decimal("120.00")


def test_graded_snapshot_materialization_facet_refuses_a_row_value_with_no_provenance() -> None:
    """Prove the facet's own defensive check, since the model already forecloses the shape.

    ``CalculationRevision`` itself enforces
    ``set(row_casilla_values) == set(row_casilla_provenance)`` at construction, so this
    inconsistent shape can never reach the facet through normal validated construction.
    ``model_construct`` bypasses that validator deliberately, to prove the facet carries
    its own belt-and-suspenders refusal rather than relying solely on an upstream
    invariant it does not itself control.
    """
    from decimal import Decimal

    from ....core import validated_casilla_id
    from ....domain.modelos import CalculationRevision, CalculationRevisionState, derive_work_unit_id
    from ..workspace import ModeloWorkspaceMaterializationProvenanceMissingError

    bucket_id = "30330300-0000-4000-8000-000000000601"
    row_casilla = validated_casilla_id("00181")
    now = datetime(2026, 7, 4, 14, 0, tzinfo=UTC)
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2022",
    )
    row_casilla_values = {(row_casilla, 1): Decimal("120.00")}
    revision = CalculationRevision.model_construct(
        calculation_revision_id="a" * 64,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        row_casilla_values=row_casilla_values,
        row_casilla_provenance={},
        casilla_values={},
        observations=(),
        source_provenance=(),
        created_at=now,
        updated_at=now,
        filing_instance_evidence=None,
    )

    with pytest.raises(ModeloWorkspaceMaterializationProvenanceMissingError, match="row_casilla_provenance"):
        graded_snapshot_materialization_facet(revision)


def test_graded_snapshot_readiness_preserves_every_axis_and_the_ledger_issue_subject() -> None:
    """Readiness is a pure axis-preserving pass-through, including the S291 subject union."""
    from ...ledger.preflight import LedgerPreflightIssue, LedgerPreflightIssueReason
    from ...state_projection import ProjectionModeloBindingRequirement, ProjectionModeloReadiness
    from ...user_profile.commands import ProfilePreflightRequirement
    from ..workspace_models import (
        ModeloWorkspaceBindingRequirementV1,
        ModeloWorkspaceLedgerPeriodSubjectV1,
        ModeloWorkspaceLedgerTransactionSubjectV1,
        ModeloWorkspaceProfileRequirementV1,
    )

    period = Period.from_year_and_code(2026, "1T")
    readiness = ProjectionModeloReadiness(
        profile_id="11111111-1111-4111-8111-111111111111",
        modelo="303",
        revision_id="2022",
        filing_year=2026,
        period=period,
        missing=(
            ProfilePreflightRequirement(
                selector="tipo_actividad",
                section_key="actividad",
                field_key="tipo",
                label="Tipo de actividad",
                legal_refs=("ley-37-1992:art-99",),
                modelos=("303",),
            ),
        ),
        profile_ready=False,
        per_operation_requirements_assessed=True,
        profile_refusal="missing activity type",
        registry_ready=True,
        registry_refusal="",
        binding_ready=False,
        missing_bindings=(
            ProjectionModeloBindingRequirement(
                binding_id="inventory-operation-0181",
                source=BindingSourceKind.INVENTORY,
                input_channel="ledger",
            ),
        ),
        ledger_preflight_required=True,
        ledger_ready=False,
        ledger_period=period,
        ledger_checked_transaction_count=3,
        ledger_issues=(
            LedgerPreflightIssue(
                transaction_id="e" * 64,
                reason=LedgerPreflightIssueReason.MISSING_CATEGORY,
                detail="missing IVA category",
            ),
            LedgerPreflightIssue(
                transaction_id="__period__",
                reason=LedgerPreflightIssueReason.UNSUPPORTED_PERIOD,
                detail="period has no date span",
            ),
        ),
        ready=False,
    )

    projected = graded_snapshot_readiness(readiness)

    assert projected.profile_id == readiness.profile_id
    assert projected.modelo == readiness.modelo
    assert projected.revision_id == readiness.revision_id
    assert projected.filing_year == readiness.filing_year
    assert projected.period == readiness.period
    assert len(projected.missing) == 1
    assert isinstance(projected.missing[0], ModeloWorkspaceProfileRequirementV1)
    assert projected.missing[0].selector == "tipo_actividad"
    assert projected.profile_ready == readiness.profile_ready
    assert projected.per_operation_requirements_assessed == readiness.per_operation_requirements_assessed
    assert projected.profile_refusal == readiness.profile_refusal
    assert projected.registry_ready == readiness.registry_ready
    assert projected.binding_ready == readiness.binding_ready
    assert len(projected.missing_bindings) == 1
    assert isinstance(projected.missing_bindings[0], ModeloWorkspaceBindingRequirementV1)
    assert projected.missing_bindings[0].binding_id == "inventory-operation-0181"
    assert projected.ledger_preflight_required == readiness.ledger_preflight_required
    assert projected.ledger_ready == readiness.ledger_ready
    assert projected.ledger_period == readiness.ledger_period
    assert projected.ledger_checked_transaction_count == readiness.ledger_checked_transaction_count
    assert projected.ready == readiness.ready

    assert len(projected.ledger_issues) == 2
    transaction_issue, period_issue = projected.ledger_issues
    assert isinstance(transaction_issue.subject, ModeloWorkspaceLedgerTransactionSubjectV1)
    assert transaction_issue.subject.transaction_id == "e" * 64
    assert isinstance(period_issue.subject, ModeloWorkspaceLedgerPeriodSubjectV1)


def test_graded_snapshot_provenance_facet_fans_out_by_linked_casilla_and_marks_unlinked_refs() -> None:
    """S290: a source ref fans out to one record per linked casilla; an unlinked ref yields one subject=None record."""
    from ....core import CalculationSourceLineageRole, validated_casilla_id
    from ....core.aggregation import BindingSourceKind
    from ....domain.modelos import CalculationSourceRef
    from ..workspace_models import ModeloWorkspaceCasillaReferenceV1

    linked_casilla = validated_casilla_id("00501")
    second_linked_casilla = validated_casilla_id("00181")

    linked_ref = CalculationSourceRef(
        resolver_id="invoice_catalogue",
        resolved_binding_source=BindingSourceKind.COLLECTIBLE_INVOICE,
        contributor_source_kind="collectible_invoice",
        contributor_binding_source=BindingSourceKind.COLLECTIBLE_INVOICE,
        lineage_role=CalculationSourceLineageRole.PRIMARY,
        source_ref="collectible_invoice:inv-0001",
        parent_source_ref=None,
        source_casilla_ids=(second_linked_casilla, linked_casilla),
    )
    unlinked_ref = CalculationSourceRef(
        resolver_id="ledger_iva_aggregation",
        resolved_binding_source=BindingSourceKind.LEDGER_IVA_AGGREGATION,
        contributor_source_kind="ledger_iva_aggregation",
        contributor_binding_source=BindingSourceKind.LEDGER_IVA_AGGREGATION,
        lineage_role=CalculationSourceLineageRole.PRIMARY,
        source_ref="transaction:tx-0001",
        parent_source_ref=None,
    )

    records = graded_snapshot_provenance_facet((linked_ref, unlinked_ref))

    assert len(records) == 3
    linked_records = [record for record in records if record.subject is not None]
    unlinked_records = [record for record in records if record.subject is None]
    assert len(linked_records) == 2
    assert len(unlinked_records) == 1
    subjects = {
        record.subject.casilla_id
        for record in linked_records
        if isinstance(record.subject, ModeloWorkspaceCasillaReferenceV1)
    }
    assert subjects == {linked_casilla, second_linked_casilla}
    assert all(record.calculation_source is linked_ref for record in linked_records)
    assert unlinked_records[0].calculation_source is unlinked_ref


def _resolved_target_with_work_unit(*, work_unit_id: str, revision_id: str = "2022"):
    from ....core import RevisionReviewStatus
    from ....domain.modelos import WorkUnitState
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
    from ....domain.modelos import (
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


def test_graded_snapshot_capabilities_reads_producer_stamps_not_derivations() -> None:
    """S287: CALCULATION_MATERIALIZATION and VERIFICATION_READINESS read what the calculate/verify producer wrote."""
    from ....domain.modelos import CalculationRevisionState
    from ..workspace_models import ModeloWorkspaceCapabilityDisposition, ModeloWorkspaceCapabilityName

    work_unit_id = "f" * 64
    target = _resolved_target_with_work_unit(work_unit_id=work_unit_id)

    # No calculation revision at all -> both calculation-derived capabilities unmeasured.
    none_capabilities = {
        c.capability: c.disposition
        for c in graded_snapshot_modelo_workspace_capabilities(target, calculation_revision=None)
    }
    assert (
        none_capabilities[ModeloWorkspaceCapabilityName.SCHEMA_INSPECTION]
        == ModeloWorkspaceCapabilityDisposition.AVAILABLE
    )
    assert (
        none_capabilities[ModeloWorkspaceCapabilityName.CALCULATION_MATERIALIZATION]
        == ModeloWorkspaceCapabilityDisposition.UNMEASURED
    )
    assert (
        none_capabilities[ModeloWorkspaceCapabilityName.VERIFICATION_READINESS]
        == ModeloWorkspaceCapabilityDisposition.UNMEASURED
    )
    assert (
        none_capabilities[ModeloWorkspaceCapabilityName.FILING_DRAFT_READINESS]
        == ModeloWorkspaceCapabilityDisposition.UNMEASURED
    )
    assert (
        none_capabilities[ModeloWorkspaceCapabilityName.FILING_EXPORT_READINESS]
        == ModeloWorkspaceCapabilityDisposition.UNMEASURED
    )

    # A BORRADOR revision exists for the exact coordinate -> materialization available, verification not yet.
    borrador_revision = _minimal_calculation_revision(
        work_unit_id=work_unit_id, state=CalculationRevisionState.BORRADOR
    )
    borrador_capabilities = {
        c.capability: c.disposition
        for c in graded_snapshot_modelo_workspace_capabilities(target, calculation_revision=borrador_revision)
    }
    assert (
        borrador_capabilities[ModeloWorkspaceCapabilityName.CALCULATION_MATERIALIZATION]
        == ModeloWorkspaceCapabilityDisposition.AVAILABLE
    )
    assert (
        borrador_capabilities[ModeloWorkspaceCapabilityName.VERIFICATION_READINESS]
        == ModeloWorkspaceCapabilityDisposition.UNMEASURED
    )

    # A VERIFICADO_COMPLETO revision -> both available.
    verified_revision = _minimal_calculation_revision(
        work_unit_id=work_unit_id, state=CalculationRevisionState.VERIFICADO_COMPLETO
    )
    verified_capabilities = {
        c.capability: c.disposition
        for c in graded_snapshot_modelo_workspace_capabilities(target, calculation_revision=verified_revision)
    }
    assert (
        verified_capabilities[ModeloWorkspaceCapabilityName.CALCULATION_MATERIALIZATION]
        == ModeloWorkspaceCapabilityDisposition.AVAILABLE
    )
    assert (
        verified_capabilities[ModeloWorkspaceCapabilityName.VERIFICATION_READINESS]
        == ModeloWorkspaceCapabilityDisposition.AVAILABLE
    )

    # A revision for a DIFFERENT work unit must never count -- exact coordinate, not merely "some revision exists".
    other_revision = _minimal_calculation_revision(
        work_unit_id="e" * 64, state=CalculationRevisionState.VERIFICADO_COMPLETO
    )
    mismatched_capabilities = {
        c.capability: c.disposition
        for c in graded_snapshot_modelo_workspace_capabilities(target, calculation_revision=other_revision)
    }
    assert (
        mismatched_capabilities[ModeloWorkspaceCapabilityName.CALCULATION_MATERIALIZATION]
        == ModeloWorkspaceCapabilityDisposition.UNMEASURED
    )
    assert (
        mismatched_capabilities[ModeloWorkspaceCapabilityName.VERIFICATION_READINESS]
        == ModeloWorkspaceCapabilityDisposition.UNMEASURED
    )


def test_graded_snapshot_schema_identity_evidence_horizon_and_contributors_over_a_real_snapshot() -> None:
    """S128: the graded schema identity/evidence horizon/contributors read the real bundled snapshot."""
    from ..workspace import (
        graded_snapshot_contributors,
        graded_snapshot_evidence_horizon,
        resolve_graded_snapshot_schema_identity,
    )

    snapshot = _real_303_snapshot()

    schema_identity = resolve_graded_snapshot_schema_identity(snapshot)
    assert schema_identity.schema_id == f"modelo-{snapshot.modelo.id}-{snapshot.revision.id}".lower()
    assert len(schema_identity.schema_fingerprint) > 0
    assert len(schema_identity.field_manifest_digest) > 0

    evidence_horizon = graded_snapshot_evidence_horizon(snapshot)
    assert evidence_horizon.source_refs == tuple(sorted(snapshot.sources))
    assert len(evidence_horizon.source_refs) > 0

    contributors = graded_snapshot_contributors()
    assert len(contributors) == 6
    contributors_again = graded_snapshot_contributors()
    assert contributors == contributors_again  # deterministic ordering


def test_resolve_graded_snapshot_result_refuses_when_the_target_has_no_calculation(
    repos,
) -> None:
    """S128: CALCULATION_UNAVAILABLE fires before REGISTRY grade admission, for a real never-calculated work unit."""
    from ....core import OutputLanguage, RegistryAuthorityGrade
    from ....domain.calculations.registry.authority import bundled_authority
    from ....domain.calculations.registry.temporal import select_revision
    from ....domain.modelos import ModeloCode, WorkUnit, derive_work_unit_id, upsert_work_unit
    from ..workspace import resolve_graded_snapshot_result
    from ..workspace_models import ModeloWorkspaceRefusalCode, ModeloWorkspaceRefusedResultV1

    work_repo, calculation_repo, _filing_repo, verification_repo, _bucket_event_repo = repos
    bucket_id = "11111111-1111-4111-8111-111111111111"
    modelo = ModeloCode("130")
    filing_year = 2026
    period = Period.from_year_and_code(filing_year, "1T")
    authority = bundled_authority()
    selected_revision = select_revision(authority.validate_modelo(modelo), filing_year=filing_year, period="1T")

    work_unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision_id=selected_revision.id,
        ),
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=selected_revision.id,
        name="130-2026-1T",
        created_at=_T0,
        updated_at=_T0,
    )
    work_repo.save(upsert_work_unit(work_repo.load(), work_unit))

    target = _visible_target(bucket_id)

    result = resolve_graded_snapshot_result(
        target,
        required_grade=RegistryAuthorityGrade.CALCULATION,
        bucket_id=bucket_id,
        catalogue_repository=work_repo,
        calculation_repository=calculation_repo,
        verification_repository=verification_repo,
        authority=authority,
        census=load_source_connectivity_census(),
        as_of=_CLOSURE_AS_OF,
        output_language=OutputLanguage.ES,
    )

    assert isinstance(result, ModeloWorkspaceRefusedResultV1)
    assert result.refusal.kind == "domain"
    assert result.refusal.code is ModeloWorkspaceRefusalCode.CALCULATION_UNAVAILABLE
    # ADR fixed point, refusal arm: a refused result carries no projection at
    # all -- structurally, not merely by omission -- so no review, stale or
    # otherwise, can ever leak through this outcome.
    assert not hasattr(result, "projection")


def test_resolve_graded_snapshot_result_refuses_target_not_found_when_no_work_unit_exists(
    repos,
) -> None:
    """An absent work unit refuses TARGET_NOT_FOUND, never CALCULATION_UNAVAILABLE.

    The prior refusal test always creates its work unit first, so it can
    never exercise this branch: a work unit that merely has no calculation is
    a different fact from no work unit existing at all, and only the first
    can be remedied by "calculate this work unit". Confirms the WORK
    selector's ``ABSENT`` state (no matching ``WorkUnit`` in the catalogue)
    reaches this admission rather than being refused upstream by the
    selector itself.
    """
    from ....core import OutputLanguage, RegistryAuthorityGrade
    from ....domain.calculations.registry.authority import bundled_authority
    from ..workspace import resolve_graded_snapshot_result
    from ..workspace_models import ModeloWorkspaceRefusalCode, ModeloWorkspaceRefusedResultV1

    work_repo, calculation_repo, _filing_repo, verification_repo, _bucket_event_repo = repos
    bucket_id = "11111111-1111-4111-8111-111111111111"
    authority = bundled_authority()
    target = _visible_target(bucket_id)

    result = resolve_graded_snapshot_result(
        target,
        required_grade=RegistryAuthorityGrade.CALCULATION,
        bucket_id=bucket_id,
        catalogue_repository=work_repo,
        calculation_repository=calculation_repo,
        verification_repository=verification_repo,
        authority=authority,
        census=load_source_connectivity_census(),
        as_of=_CLOSURE_AS_OF,
        output_language=OutputLanguage.ES,
    )

    assert isinstance(result, ModeloWorkspaceRefusedResultV1)
    assert result.refusal.kind == "domain"
    assert result.refusal.code is ModeloWorkspaceRefusalCode.TARGET_NOT_FOUND
    assert "create a work unit" in result.refusal.reconsideration_condition
    assert not hasattr(result, "projection")


def test_resolve_graded_snapshot_result_assembles_a_complete_projection_over_a_real_calculation(
    repos,
) -> None:
    """S128: the full assembly over a real work unit, calculation, and verification report."""
    from decimal import Decimal

    from ....core import ModeloWorkProgressState, OutputLanguage, RegistryAuthorityGrade
    from ....domain.calculations.registry.authority import bundled_authority
    from ....domain.calculations.registry.temporal import select_revision
    from ....domain.modelos import ModeloCode, WorkUnit, derive_work_unit_id, upsert_work_unit
    from ..workspace import resolve_graded_snapshot_result
    from ..workspace_models import ModeloWorkspaceGradedSnapshotResultV1
    from ._file_flow_support import (
        DEFAULT_130_BASELINE_INPUTS,
        DEFAULT_130_BINDING_VALUES,
        calculate_modelo_revision,
        verify_revision,
    )

    work_repo, calculation_repo, filing_repo, verification_repo, bucket_event_repo = repos
    bucket_id = "11111111-1111-4111-8111-111111111111"
    modelo = ModeloCode("130")
    filing_year = 2026
    period = Period.from_year_and_code(filing_year, "1T")
    authority = bundled_authority()
    selected_revision = select_revision(authority.validate_modelo(modelo), filing_year=filing_year, period="1T")

    work_unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision_id=selected_revision.id,
        ),
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=selected_revision.id,
        name="130-2026-1T",
        created_at=_T0,
        updated_at=_T0,
    )
    work_repo.save(upsert_work_unit(work_repo.load(), work_unit))

    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=DEFAULT_130_BASELINE_INPUTS,
        binding_values={
            **DEFAULT_130_BINDING_VALUES,
            "modelo-130-actividad-economica-ingresos-cumulative": Decimal("9000"),
        },
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        bucket_event_repository=bucket_event_repo,
    )
    verify_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        verification_repository=verification_repo,
        filing_repository=filing_repo,
        bucket_event_repository=bucket_event_repo,
        clock=revision.updated_at,
    )

    target = _visible_target(bucket_id)

    result = resolve_graded_snapshot_result(
        target,
        required_grade=RegistryAuthorityGrade.CALCULATION,
        bucket_id=bucket_id,
        catalogue_repository=work_repo,
        calculation_repository=calculation_repo,
        verification_repository=verification_repo,
        authority=authority,
        census=load_source_connectivity_census(),
        as_of=_CLOSURE_AS_OF,
        output_language=OutputLanguage.ES,
    )

    assert isinstance(result, ModeloWorkspaceGradedSnapshotResultV1)
    projection = result.projection
    assert projection.target.modelo == modelo
    assert projection.work_review.review is not None
    assert projection.work_review.review.calculation_revision_id == revision.calculation_revision_id
    assert projection.work_review.review.progress.state is ModeloWorkProgressState.COMPLETE
    assert projection.materialization_facet is not None
    assert projection.materialization_facet.records  # a real, non-empty materialization facet
    assert projection.provenance_facet is not None
    assert projection.schema_facet.records  # a real, non-empty graded schema facet
    assert len(projection.capabilities) == len(ModeloWorkspaceCapabilityName)

    # ADR fixed point: BOUNDED_REVIEW is a pass-through, never a second,
    # independently maintained review join. The projection's work_review MUST
    # equal, field for field, the exact record the sole canonical producer
    # (build_modelo_work_review) assembles for the SAME coordinate and the
    # SAME repositories -- not a spot-checked subset of fields, since a
    # future edit that reinterprets findings ordering, blockers, origin or
    # evidence references would red nothing under a subset comparison.
    from ..work_review import build_modelo_work_review

    canonical_review = build_modelo_work_review(
        bucket_id,
        modelo,
        filing_year,
        period,
        authority=authority,
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        verification_repository=verification_repo,
    )
    assert projection.work_review.review == canonical_review

    # Round-trip through JSON must reproduce the identical result.
    reloaded = ModeloWorkspaceGradedSnapshotResultV1.model_validate_json(result.model_dump_json())
    assert reloaded == result


def test_resolve_graded_snapshot_result_refuses_authority_grade_unavailable(
    repos,
) -> None:
    """S128: a real revision whose declared grade cannot satisfy the requested one refuses honestly.

    Modelo 117's ``2019-y-siguientes`` revision declares ``calculation``
    authority (``revision.toml``); requesting ``filing`` cannot be satisfied.
    The work unit's ``current_calculation_revision_id`` is set directly
    (never through a real calculate run) because this refusal fires around
    the REGISTRY capture, strictly before the CALCULATION port is ever
    touched -- the work unit only has to carry a non-``None`` id to pass the
    earlier ``CALCULATION_UNAVAILABLE`` gate.
    """
    from ....core import OutputLanguage, RegistryAuthorityGrade
    from ....domain.calculations.registry.authority import bundled_authority
    from ....domain.calculations.registry.temporal import select_revision
    from ....domain.modelos import ModeloCode, WorkUnit, derive_work_unit_id, upsert_work_unit
    from ..workspace import resolve_graded_snapshot_result
    from ..workspace_models import ModeloWorkspaceRefusalCode, ModeloWorkspaceRefusedResultV1

    work_repo, calculation_repo, _filing_repo, verification_repo, _bucket_event_repo = repos
    bucket_id = "11111111-1111-4111-8111-111111111111"
    modelo = ModeloCode("117")
    filing_year = 2026
    period = Period.from_year_and_code(filing_year, "1T")
    authority = bundled_authority()
    selected_revision = select_revision(authority.validate_modelo(modelo), filing_year=filing_year, period="1T")
    assert selected_revision.authority_grade == RegistryAuthorityGrade.CALCULATION

    work_unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision_id=selected_revision.id,
        ),
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=selected_revision.id,
        name="117-2026-1T",
        current_calculation_revision_id="a" * 64,
        created_at=_T0,
        updated_at=_T0,
    )
    work_repo.save(upsert_work_unit(work_repo.load(), work_unit))

    target = _visible_target_for(modelo, filing_year=filing_year, period="1T", bucket_id=bucket_id)

    result = resolve_graded_snapshot_result(
        target,
        required_grade=RegistryAuthorityGrade.FILING,
        bucket_id=bucket_id,
        catalogue_repository=work_repo,
        calculation_repository=calculation_repo,
        verification_repository=verification_repo,
        authority=authority,
        census=load_source_connectivity_census(),
        as_of=_CLOSURE_AS_OF,
        output_language=OutputLanguage.ES,
    )

    assert isinstance(result, ModeloWorkspaceRefusedResultV1)
    assert result.refusal.kind == "domain"
    assert result.refusal.code is ModeloWorkspaceRefusalCode.AUTHORITY_GRADE_UNAVAILABLE
    # ADR fixed point, refusal arm: a refused result carries no projection at
    # all -- structurally, not merely by omission -- so no review, stale or
    # otherwise, can ever leak through this outcome.
    assert not hasattr(result, "projection")


def test_resolve_graded_snapshot_result_reraises_a_non_grade_registry_validation_error(
    repos,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S128: only the typed SNAPSHOT_AUTHORITY_GRADE_SUFFICIENT condition maps to AUTHORITY_GRADE_UNAVAILABLE.

    ``RegistryValidationError`` is a broad type; a catch that maps every
    instance of it to ``AUTHORITY_GRADE_UNAVAILABLE`` would silently report a
    genuine, unrelated registry defect as a grade problem, sending an
    operator to the wrong remedy and hiding the real one behind a green
    happy-path test. ``TREE_QUIESCENT`` (a real, typed condition this error
    carries in production for a concurrent registry-tree write) is not
    reachable through the bundled fixture registry on demand, so this proof
    monkeypatches the ONE call `resolve_graded_snapshot_result` makes for
    REGISTRY -- ``ValidatedRegistryAuthority.capture_law_selected_projection``
    on this specific, real authority instance -- to raise that real, typed
    error instead of admitting a snapshot. No data is faked and no other
    behaviour is touched; only the one failure path this bundled fixture
    registry cannot otherwise exercise is forced, to prove the except clause
    discriminates by condition rather than by type.
    """
    from ....core import OutputLanguage, RegistryAuthorityGrade
    from ....domain.calculations.registry.authority import bundled_authority
    from ....domain.calculations.registry.errors import (
        RegistryFailureClassification,
        RegistryFailureCondition,
        RegistryValidationError,
    )
    from ....domain.calculations.registry.temporal import select_revision
    from ....domain.modelos import ModeloCode, WorkUnit, derive_work_unit_id, upsert_work_unit
    from ..workspace import resolve_graded_snapshot_result

    work_repo, calculation_repo, _filing_repo, verification_repo, _bucket_event_repo = repos
    bucket_id = "11111111-1111-4111-8111-111111111111"
    modelo = ModeloCode("130")
    filing_year = 2026
    period = Period.from_year_and_code(filing_year, "1T")
    authority = bundled_authority()
    selected_revision = select_revision(authority.validate_modelo(modelo), filing_year=filing_year, period="1T")

    work_unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision_id=selected_revision.id,
        ),
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=selected_revision.id,
        name="130-2026-1T",
        current_calculation_revision_id="a" * 64,
        created_at=_T0,
        updated_at=_T0,
    )
    work_repo.save(upsert_work_unit(work_repo.load(), work_unit))

    def _raise_unrelated_registry_failure(*args: object, **kwargs: object) -> None:
        raise RegistryValidationError(
            "registry tree is mid-write; retry once quiescent",
            registry_failure=RegistryFailureClassification(
                condition=RegistryFailureCondition.TREE_QUIESCENT,
                facts={"modelo": str(modelo)},
            ),
        )

    monkeypatch.setattr(type(authority), "capture_law_selected_projection", _raise_unrelated_registry_failure)

    target = _visible_target_for(modelo, filing_year=filing_year, period="1T", bucket_id=bucket_id)

    with pytest.raises(RegistryValidationError) as excinfo:
        resolve_graded_snapshot_result(
            target,
            required_grade=RegistryAuthorityGrade.CALCULATION,
            bucket_id=bucket_id,
            catalogue_repository=work_repo,
            calculation_repository=calculation_repo,
            verification_repository=verification_repo,
            authority=authority,
            census=load_source_connectivity_census(),
            as_of=_CLOSURE_AS_OF,
            output_language=OutputLanguage.ES,
        )

    assert excinfo.value.registry_failure is not None
    assert excinfo.value.registry_failure.condition is RegistryFailureCondition.TREE_QUIESCENT


def test_resolve_graded_snapshot_result_reads_the_work_catalogue_before_any_write(
    repos,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """S128: the assembly's every work-unit-catalogue event, scoped to the call, is a read.

    This does NOT assert the total work-unit-catalogue READ count across the
    whole assembly is 1: BOUNDED_REVIEW delegates to the real
    ``build_modelo_work_review``/cross-period dependency machinery, which
    genuinely performs SEVERAL of its own catalogue reads (observed: 10, not
    1) as part of computing a review -- so a bare read count conflates
    BOUNDED_REVIEW's own legitimate multi-read behaviour with a hypothetical
    duplicate WORK-contributor re-capture; the two produce the identical log
    line and cannot be told apart from count alone. The WORK-then-REGISTRY
    core's OWN single-read property is already proven in isolation by
    ``test_capture_with_a_grade_admits_a_registry_snapshot_reading_work_and_registry_exactly_once``,
    which exercises that exact function with no BOUNDED_REVIEW capture in
    play.

    What THIS test proves instead: every work-unit-catalogue event observed
    during the call, properly scoped to ``caplog.records`` (never the
    unscoped terminal "Captured log call" dump, which also carries this
    test's own pre-``caplog.clear()`` setup -- calculate and verify -- and
    is easy to misread as in-call activity), is a load, never a save.
    Verified directly: the scoped ``catalogue_records`` for this exact
    fixture is 10 loads and zero saves, so ``resolve_graded_snapshot_result``
    over this target performs no work-unit-catalogue write at all.
    """
    import logging
    from decimal import Decimal

    from ....core import OutputLanguage, RegistryAuthorityGrade
    from ....domain.calculations.registry.authority import bundled_authority
    from ....domain.calculations.registry.temporal import select_revision
    from ....domain.modelos import ModeloCode, WorkUnit, derive_work_unit_id, upsert_work_unit
    from ..workspace import resolve_graded_snapshot_result
    from ..workspace_models import ModeloWorkspaceGradedSnapshotResultV1
    from ._file_flow_support import DEFAULT_130_BASELINE_INPUTS, DEFAULT_130_BINDING_VALUES
    from ._file_flow_support import calculate_modelo_revision as _calc
    from ._file_flow_support import verify_revision as _verify

    work_repo, calculation_repo, filing_repo, verification_repo, bucket_event_repo = repos
    bucket_id = "11111111-1111-4111-8111-111111111111"
    modelo = ModeloCode("130")
    filing_year = 2026
    period = Period.from_year_and_code(filing_year, "1T")
    authority = bundled_authority()
    selected_revision = select_revision(authority.validate_modelo(modelo), filing_year=filing_year, period="1T")

    work_unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision_id=selected_revision.id,
        ),
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=selected_revision.id,
        name="130-2026-1T",
        created_at=_T0,
        updated_at=_T0,
    )
    work_repo.save(upsert_work_unit(work_repo.load(), work_unit))

    revision = _calc(
        work_unit.work_unit_id,
        casilla_inputs=DEFAULT_130_BASELINE_INPUTS,
        binding_values={
            **DEFAULT_130_BINDING_VALUES,
            "modelo-130-actividad-economica-ingresos-cumulative": Decimal("9000"),
        },
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        bucket_event_repository=bucket_event_repo,
    )
    _verify(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        verification_repository=verification_repo,
        filing_repository=filing_repo,
        bucket_event_repository=bucket_event_repo,
        clock=revision.updated_at,
    )

    target = _visible_target_for(modelo, filing_year=filing_year, period="1T", bucket_id=bucket_id)

    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger="cadrumo.adapters.persistence.profile.modelos_work_units"):
        result = resolve_graded_snapshot_result(
            target,
            required_grade=RegistryAuthorityGrade.CALCULATION,
            bucket_id=bucket_id,
            catalogue_repository=work_repo,
            calculation_repository=calculation_repo,
            verification_repository=verification_repo,
            authority=authority,
            census=load_source_connectivity_census(),
            as_of=_CLOSURE_AS_OF,
            output_language=OutputLanguage.ES,
        )

    assert isinstance(result, ModeloWorkspaceGradedSnapshotResultV1)
    catalogue_messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "cadrumo.adapters.persistence.profile.modelos_work_units"
    ]
    catalogue_records = [
        message
        for message in catalogue_messages
        if "loaded work-unit catalogue" in message or "saved work-unit catalogue" in message
    ]
    assert catalogue_records  # the assembly touches the work-unit catalogue at all
    assert all("loaded work-unit catalogue" in message for message in catalogue_records)


def test_resolve_graded_snapshot_result_baseline_reflects_a_real_contributor_change(
    repos,
) -> None:
    """S128 epoch consistency: a real change to one contributor must change the pinned baseline.

    Two identical calls over unchanged data must agree byte-for-byte
    (deterministic assembly); a real second calculation on the SAME work
    unit changes ``current_calculation_revision_id``, which the CALCULATION
    contributor's own stamp/epoch must reflect -- and therefore the
    assembled ``contributor_epoch_digest``/``baseline`` must differ, never
    silently reuse the first call's pinned coordinate.
    """
    from decimal import Decimal

    from ....core import OutputLanguage, RegistryAuthorityGrade
    from ....domain.calculations.registry.authority import bundled_authority
    from ....domain.calculations.registry.temporal import select_revision
    from ....domain.modelos import ModeloCode, WorkUnit, derive_work_unit_id, upsert_work_unit
    from ..workspace import resolve_graded_snapshot_result
    from ..workspace_models import ModeloWorkspaceGradedSnapshotResultV1
    from ._file_flow_support import DEFAULT_130_BASELINE_INPUTS, DEFAULT_130_BINDING_VALUES
    from ._file_flow_support import calculate_modelo_revision as _calc
    from ._file_flow_support import verify_revision as _verify

    work_repo, calculation_repo, filing_repo, verification_repo, bucket_event_repo = repos
    bucket_id = "11111111-1111-4111-8111-111111111111"
    modelo = ModeloCode("130")
    filing_year = 2026
    period = Period.from_year_and_code(filing_year, "1T")
    authority = bundled_authority()
    selected_revision = select_revision(authority.validate_modelo(modelo), filing_year=filing_year, period="1T")

    work_unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision_id=selected_revision.id,
        ),
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=selected_revision.id,
        name="130-2026-1T",
        created_at=_T0,
        updated_at=_T0,
    )
    work_repo.save(upsert_work_unit(work_repo.load(), work_unit))

    first_revision = _calc(
        work_unit.work_unit_id,
        casilla_inputs=DEFAULT_130_BASELINE_INPUTS,
        binding_values={
            **DEFAULT_130_BINDING_VALUES,
            "modelo-130-actividad-economica-ingresos-cumulative": Decimal("9000"),
        },
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        bucket_event_repository=bucket_event_repo,
    )
    _verify(
        first_revision.calculation_revision_id,
        revision=first_revision,
        work_unit=work_unit,
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        verification_repository=verification_repo,
        filing_repository=filing_repo,
        bucket_event_repository=bucket_event_repo,
        clock=first_revision.updated_at,
    )

    target = _visible_target_for(modelo, filing_year=filing_year, period="1T", bucket_id=bucket_id)

    def _resolve() -> ModeloWorkspaceGradedSnapshotResultV1:
        result = resolve_graded_snapshot_result(
            target,
            required_grade=RegistryAuthorityGrade.CALCULATION,
            bucket_id=bucket_id,
            catalogue_repository=work_repo,
            calculation_repository=calculation_repo,
            verification_repository=verification_repo,
            authority=authority,
            census=load_source_connectivity_census(),
            as_of=_CLOSURE_AS_OF,
            output_language=OutputLanguage.ES,
        )
        assert isinstance(result, ModeloWorkspaceGradedSnapshotResultV1)
        return result

    first_result = _resolve()
    second_result = _resolve()
    assert first_result.projection.baseline == second_result.projection.baseline
    assert (
        first_result.projection.baseline.contributor_epoch_digest
        == second_result.projection.baseline.contributor_epoch_digest
    )

    # A real second calculation on the same work unit is a genuine change to
    # the CALCULATION contributor's own stamp/epoch -- proving the baseline
    # is pinned from the captures, never re-derived after the fact.
    second_revision = _calc(
        work_unit.work_unit_id,
        casilla_inputs=DEFAULT_130_BASELINE_INPUTS,
        binding_values={
            **DEFAULT_130_BINDING_VALUES,
            "modelo-130-actividad-economica-ingresos-cumulative": Decimal("15000"),
        },
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        bucket_event_repository=bucket_event_repo,
    )
    assert second_revision.calculation_revision_id != first_revision.calculation_revision_id
    updated_work_unit = work_repo.load().work_units[work_unit.work_unit_id]
    assert updated_work_unit.current_calculation_revision_id == second_revision.calculation_revision_id

    third_result = _resolve()
    assert third_result.projection.baseline != first_result.projection.baseline
    assert (
        third_result.projection.baseline.contributor_epoch_digest
        != first_result.projection.baseline.contributor_epoch_digest
    )


def test_workspace_assembly_has_one_public_module_and_no_private_or_package_binding_remnant() -> None:
    """S129: the assembly/dispatch module is the sole public home, with no package binding.

    Mirrors ``test_workspace_models_have_one_public_module_and_no_private_or_package_binding_remnant``
    and ``test_workspace_producers_have_one_public_module_and_no_private_or_package_binding_remnant``
    -- the same fixed point S171/S172 proved for the model and producer
    families, applied to the assembly/dispatch family S128/S129 own.
    ``workspace.py`` never had a private predecessor (unlike
    ``_workspace_models.py``/``_workspace_producers.py``), so there is no
    retired private module to assert against; what remains to prove is that
    ``application.modelo`` stays inert with respect to every Workspace
    assembly symbol, and that the two private paths S128's own module
    docstring names as forbidden (``_workspace.py``, a private predecessor of
    this module, and ``_workspace_projection.py``, an explicitly rejected
    intermediate design) have not reappeared anywhere in the tracked tree.
    """
    import importlib

    public_module = importlib.import_module("cadrumo.application.modelo.workspace")
    package = importlib.import_module("cadrumo.application.modelo")

    assert public_module.resolve_static_inspection_result is resolve_static_inspection_result
    assert resolve_static_inspection_result.__module__ == public_module.__name__
    assert package.__all__ == ()
    assert not hasattr(package, "resolve_static_inspection_result")
    assert not hasattr(package, "resolve_graded_snapshot_result")
    assert not hasattr(package, "ModeloWorkspaceRevisionAxes")


def test_workspace_assembly_forbidden_private_paths_have_not_reappeared_in_the_tracked_tree() -> None:
    """S129 zero-remnant fixed point: enumerate TRACKED files, never walk the filesystem.

    A gitignored mirror or a peer's in-flight deletion can make a filesystem
    walk report a phantom remnant or silently skip a real one; ``git
    ls-files`` is the one census that answers "what does this tree actually
    track" regardless of either. Scoped to ``src``, ``docs``, and ``dev`` --
    the same scope the sibling model/producer fixed-point tests use.
    """
    import subprocess

    repository = Path(__file__).resolve().parents[5]
    forbidden_module_stems = ("_workspace_projection", "_workspace")
    tracked = subprocess.run(
        ("git", "ls-files", "-z", "--", "src", "docs", "dev"),  # noqa: S607
        capture_output=True,
        check=True,
        cwd=repository,
        text=True,
    ).stdout.split(chr(0))
    modelo_package = "src/cadrumo/application/modelo/"
    remnant_paths = tuple(
        entry
        for entry in tracked
        if entry.startswith(modelo_package)
        and entry[len(modelo_package) :] in ("_workspace_projection.py", "_workspace.py")
    )
    assert not remnant_paths, forbidden_module_stems

    scanned_paths = tuple(
        sorted(
            path
            for entry in tracked
            if entry.endswith((".py", ".rst", ".toml"))
            # A path git still tracks can be absent from the working tree
            # while a peer's deletion is in flight. It carries no content to
            # scan, and reading it would fail the gate on someone else's
            # staging state rather than on a genuine remnant.
            if (path := repository / entry).is_file()
        ),
    )
    # workspace.py's own module docstring names "_workspace_projection.py" once,
    # deliberately: it records the REJECTED intermediate design S128 chose
    # against, the same way this test's own docstring names it too. Neither is
    # a stale reference thinking that module exists; both are excluded from
    # the scan for that reason, and nowhere else in the tracked tree may name it.
    excluded_paths = {Path(__file__).resolve(), (repository / "src/cadrumo/application/modelo/workspace.py").resolve()}
    prose_remnants = tuple(
        path.relative_to(repository)
        for path in scanned_paths
        if path.resolve() not in excluded_paths
        # Match the forbidden module as a whole filename, not a substring: the
        # live conformance suite legitimately names test_workspace_projection.py,
        # which CONTAINS the rejected _workspace_projection.py and would otherwise
        # red this gate on correct code.
        and re.search(r"(?<![A-Za-z0-9_])_workspace_projection\.py", path.read_text(encoding="utf-8"))
    )
    assert not prose_remnants
