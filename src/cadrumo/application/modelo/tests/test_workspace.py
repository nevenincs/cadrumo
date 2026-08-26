"""Integration contracts for the Workspace V1 WORK-then-REGISTRY capture core."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.modelos import WorkUnit
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.secure_sql import isolated_runtime_profile
from .._work_lifecycle import create_work_unit
from ..work_addressing import ModeloWorkRegistryYearMismatchError
from ..workspace import (
    STATIC_INSPECTION_WORK_REVIEW_FACET,
    ModeloWorkspaceStaleCursorError,
    capture_modelo_workspace_locale_summary,
    capture_modelo_workspace_target_axes,
    capture_modelo_workspace_target_captures,
    formula_operand_references_for_casilla,
    modelo_work_selector_request_for_target,
    paginate_static_inspection_schema_facet,
    relation_source_endpoints_for_casilla,
    relation_target_endpoints_for_binding,
    resolve_modelo_workspace_target,
    resolve_static_inspection_baseline,
    resolve_static_inspection_schema_identity,
    static_inspection_binding_schema_records,
    static_inspection_casilla_schema_records,
    static_inspection_contributors,
    static_inspection_evidence_horizon,
    static_inspection_formula_schema_records,
    static_inspection_modelo_workspace_capabilities,
    static_inspection_parameter_schema_records,
    static_inspection_relation_schema_records,
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
    assert present_target.requested_revision_assertion.disposition == ModeloWorkspaceRevisionAssertionDisposition.MATCHED

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
    assert identity.field_manifest_digest == generate_modelo_workspace_field_manifest_for_inspection(inspection).manifest_digest


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

    work_capture, registry_capture, axes = capture_modelo_workspace_target_captures(
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

    from ..workspace_producers import ModeloWorkspaceLocaleCataloguePortV1
    from ....domain.calculations.registry.modelo_localization import revision_locale_key

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
    work_capture, registry_capture, axes = capture_modelo_workspace_target_captures(
        _visible_target(bucket_id),
        bucket_id=bucket_id,
        catalogue_repository=repository,
        authority=authority,
    )
    resolution = work_capture.projection
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


def test_static_inspection_binding_schema_records_use_the_real_binding_definitions() -> None:
    from ..workspace_models import ModeloWorkspaceBindingReferenceV1, ModeloWorkspaceTechnicalLabelV1

    inspection = _real_303_inspection()
    records = static_inspection_binding_schema_records(inspection)

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
    records = static_inspection_formula_schema_records(inspection)

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
    records = static_inspection_relation_schema_records(inspection)

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
    records = static_inspection_parameter_schema_records(inspection)

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
