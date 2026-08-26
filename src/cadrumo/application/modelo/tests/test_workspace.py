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
    capture_modelo_workspace_locale_summary,
    capture_modelo_workspace_target_axes,
    formula_operand_references_for_casilla,
    modelo_work_selector_request_for_target,
    relation_source_endpoints_for_casilla,
    relation_target_endpoints_for_binding,
    resolve_modelo_workspace_target,
    static_inspection_modelo_workspace_capabilities,
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
