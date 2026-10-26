"""Real persistence and registry coverage for the modelo work review projection."""

from __future__ import annotations

import importlib
from decimal import Decimal

import pytest
from pydantic import ValidationError

from cadrumo.adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    load_test_profile_record,
    replace_test_profile_record,
)
from cadrumo.application.modelo.action_errors import CalculationRevisionNotFoundError, StoredCalculationDriftError
from cadrumo.application.modelo.calculation_actions import calculate_modelo_revision
from cadrumo.application.modelo.work_addressing import ModeloExactWorkUnitTarget
from cadrumo.application.modelo.work_review import (
    ModeloWorkOriginAnomaly,
    ModeloWorkProgress,
    ModeloWorkProgressDenominator,
    ModeloWorkReview,
    build_modelo_work_review,
    capture_modelo_work_review,
    read_modelo_work_review_current_coordinate,
)
from cadrumo.application.modelo.workspace import resolve_graded_snapshot_result
from cadrumo.application.modelo.workspace_models import (
    ModeloWorkspaceCapabilityDisposition,
    ModeloWorkspaceCapabilityName,
    ModeloWorkspaceExactWorkUnitTargetV1,
    ModeloWorkspaceGradedSnapshotResultV1,
)
from cadrumo.application.modelo.workspace_producers import (
    MODELO_WORKSPACE_BOUNDED_REVIEW_PRODUCER_CONTRACT_V1,
    ModeloWorkspaceBoundedReviewPortV1,
    ModeloWorkspaceContributorKindV1,
)
from cadrumo.application.producer_capture import ProducerCaptureError
from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.modelo_work_progress_state import ModeloWorkProgressState
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.bindings import CasillaObservation
from cadrumo.domain.calculations.registry.runtime_graph import revision_date_binding_ids
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef
from cadrumo.domain.calculations.row_source_identity import RowSourceIdentity
from cadrumo.domain.filing.schema import ModeloValueKind
from cadrumo.domain.modelos.calculation_repository import (
    CalculationRevisionPersistenceError,
    upsert_calculation_revision,
)
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
    derive_calculation_revision_id_from_revision,
)
from cadrumo.domain.modelos.codes import ModeloCode
from cadrumo.domain.modelos.repository import upsert_work_unit
from cadrumo.domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
    VerificationReport,
    derive_verification_report_id,
)
from cadrumo.domain.modelos.verification_repository import upsert_verification_report
from cadrumo.domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from cadrumo.domain.user_profile.values import UserProfileFact
from cadrumo.entrypoints.adapter_composition import build_state_projection_read_ports
from cadrumo.entrypoints.tests.profile_persistence.file_flow_test_support import (
    DEFAULT_130_BASELINE_INPUTS,
    DEFAULT_130_BINDING_VALUES,
    M130_CARRY_FORWARD_CASILLA,
    M130_INCOME_CASILLA,
    M130_NET_RESULT_CASILLA,
    T0,
    Repos,
    calculation_ports_for_test,
    verify_revision,
)

from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]
_BUCKET_ID = "11111111-1111-4111-8111-111111111111"
_M130 = ModeloCode("130")
_M130_INCOME_BINDING = "modelo-130-actividad-economica-ingresos-cumulative"


def test_review_projection_has_one_public_defining_module_and_no_package_facade() -> None:
    """The application package cannot become a second home for review symbols."""
    namespace = importlib.import_module("..", package=__package__)
    review_symbols = (
        "BlockerRef",
        "ModeloWorkBindingOrigin",
        "ModeloWorkFormulaOrigin",
        "ModeloWorkOriginAnomaly",
        "ModeloWorkProgress",
        "ModeloWorkProgressDenominator",
        "ModeloWorkRelationConsumption",
        "ModeloWorkReview",
        "ModeloWorkReviewCasilla",
        "build_modelo_work_review",
    )

    assert set(review_symbols).isdisjoint(vars(namespace))
    assert ModeloWorkReview.__module__ == "cadrumo.application.modelo.work_review"
    assert build_modelo_work_review.__module__ == "cadrumo.application.modelo.work_review"


def _persist_work_unit(
    repos: Repos,
    *,
    modelo: ModeloCode = _M130,
    filing_year: int = 2026,
    period_code: str = "1T",
) -> WorkUnit:
    work_repo, _, _, _, _ = repos
    period = Period.from_year_and_code(filing_year, period_code)
    authority = published_authority_operation()
    selected_revision = authority.revision_for_context(
        modelo,
        filing_year=filing_year,
        period=period.registry_token,
    )
    revision_id = authority.snapshot(
        modelo,
        filing_year=filing_year,
        period=period.registry_token,
        revision_id=selected_revision.id,
        grade=selected_revision.effective_authority_grade,
    ).revision.id
    unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        name="130-2026-1T",
        created_at=T0,
        updated_at=T0,
    )
    work_repo.save(upsert_work_unit(work_repo.load(), unit))
    return unit


def test_a_work_review_capture_carries_exactly_the_built_review_and_stays_current(repos: Repos) -> None:
    work_repo, calculation_repo, _, verification_repo, _ = repos
    work_unit = _persist_work_unit(repos)
    target = (work_unit.bucket_id, work_unit.modelo, work_unit.filing_year, work_unit.period)
    stores = {
        "work_unit_repository": work_repo,
        "calculation_repository": calculation_repo,
        "verification_repository": verification_repo,
    }

    with bundled_indexed_authority().operation() as operation:
        built = build_modelo_work_review(
            *target,
            operation=operation,
            work_unit_repository=work_repo,
            calculation_repository=calculation_repo,
            verification_repository=verification_repo,
        )
        captured = capture_modelo_work_review(*target, operation=operation, **stores)
        again = capture_modelo_work_review(*target, operation=operation, **stores)
        current = read_modelo_work_review_current_coordinate(*target, operation=operation, **stores)

    assert captured.value == built
    assert again.generation == captured.generation
    assert captured.require_current(current) is captured


def test_the_bounded_review_port_stamps_its_contract_over_the_captured_review(repos: Repos) -> None:
    work_repo, calculation_repo, _, verification_repo, _ = repos
    work_unit = _persist_work_unit(repos)

    with bundled_indexed_authority().operation() as operation:
        port = ModeloWorkspaceBoundedReviewPortV1(
            bucket_id=work_unit.bucket_id,
            modelo=work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period,
            operation=operation,
            work_unit_repository=work_repo,
            calculation_repository=calculation_repo,
            verification_repository=verification_repo,
        )
        contributed = port.capture_projection_with_epoch()
        built = build_modelo_work_review(
            work_unit.bucket_id,
            work_unit.modelo,
            work_unit.filing_year,
            work_unit.period,
            operation=operation,
            work_unit_repository=work_repo,
            calculation_repository=calculation_repo,
            verification_repository=verification_repo,
        )

    assert contributed.projection == built
    assert contributed.stamp.contributor_kind is ModeloWorkspaceContributorKindV1.BOUNDED_REVIEW
    assert contributed.epoch.owner == MODELO_WORKSPACE_BOUNDED_REVIEW_PRODUCER_CONTRACT_V1.contributor.owner


def test_a_work_review_capture_refuses_as_not_current_after_an_interleaved_write(repos: Repos) -> None:
    work_repo, calculation_repo, _, verification_repo, _ = repos
    work_unit = _persist_work_unit(repos)
    target = (work_unit.bucket_id, work_unit.modelo, work_unit.filing_year, work_unit.period)
    stores = {
        "work_unit_repository": work_repo,
        "calculation_repository": calculation_repo,
        "verification_repository": verification_repo,
    }

    with bundled_indexed_authority().operation() as operation:
        captured = capture_modelo_work_review(*target, operation=operation, **stores)
        _persist_work_unit(repos, period_code="2T")
        moved = read_modelo_work_review_current_coordinate(*target, operation=operation, **stores)

    with pytest.raises(ProducerCaptureError) as refusal:
        captured.require_current(moved)
    assert refusal.value.translated_message == "errors.refused.producer_capture_not_current"


_M100 = ModeloCode("100")
_M100_BOOLEAN_BINDING = "renta-profile-has-economic-activity"
"""Declared on the boolean value channel by the Modelo 100 2025 registry revision."""


def _persist_m100_revision_with_override(repos: Repos, raw_value: str) -> WorkUnit:
    """Persist a Modelo 100 revision whose boolean-channel binding override holds ``raw_value``."""
    work_repo, calculation_repo, _, _, _ = repos
    unit = _persist_work_unit(repos, modelo=_M100, filing_year=2025, period_code="0A")
    overrides = {_M100_BOOLEAN_BINDING: raw_value}
    revision_id = derive_calculation_revision_id(
        work_unit_id=unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides=overrides,
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=unit.modelo,
            revision_id=unit.revision_id,
            modelo_year=unit.filing_year,
            period=unit.period.registry_token,
        ),
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={},
        binding_overrides=overrides,
        casilla_values={},
        created_at=T0,
        updated_at=T0,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    calculation_repo.save(upsert_calculation_revision(calculation_repo.load(), revision))
    pointed = unit.model_copy(update={"current_calculation_revision_id": revision_id})
    work_repo.save(upsert_work_unit(work_repo.load(), pointed))
    return pointed


@pytest.mark.parametrize("truth", ["true", "false"])
@pytest.mark.parametrize("supplied_catalogue", [False, True])
def test_the_review_reads_a_persisted_boolean_binding_as_a_truth_value(
    repos: Repos, truth: str, supplied_catalogue: bool
) -> None:
    """The replay writer stores a boolean-channel binding as a truth token, not a quantity."""
    work_repo, calculation_repo, _, verification_repo, _ = repos
    unit = _persist_m100_revision_with_override(repos, truth)

    with bundled_indexed_authority().operation() as operation:
        review = build_modelo_work_review(
            unit.bucket_id,
            unit.modelo,
            unit.filing_year,
            unit.period,
            operation=operation,
            work_unit_repository=work_repo,
            calculation_repository=calculation_repo,
            verification_repository=verification_repo,
            calculation_catalogue=calculation_repo.load(operation=operation) if supplied_catalogue else None,
        )

    assert review.calculation_revision_id == unit.current_calculation_revision_id


@pytest.mark.parametrize("supplied_catalogue", [False, True])
def test_a_boolean_binding_holding_no_truth_value_still_refuses_as_stored_drift(
    repos: Repos, supplied_catalogue: bool
) -> None:
    """Skipping truth tokens must not let an unreadable stored value through."""
    work_repo, calculation_repo, _, verification_repo, _ = repos
    unit = _persist_m100_revision_with_override(repos, "maybe")

    with bundled_indexed_authority().operation() as operation, pytest.raises(StoredCalculationDriftError):
        build_modelo_work_review(
            unit.bucket_id,
            unit.modelo,
            unit.filing_year,
            unit.period,
            operation=operation,
            work_unit_repository=work_repo,
            calculation_repository=calculation_repo,
            verification_repository=verification_repo,
            calculation_catalogue=calculation_repo.load(operation=operation) if supplied_catalogue else None,
        )


def test_a_supplied_empty_catalogue_refuses_a_missing_head_without_reloading(repos: Repos) -> None:
    work_repo, calculation_repo, _, verification_repo, _ = repos
    unit = _persist_m100_revision_with_override(repos, "true")

    with bundled_indexed_authority().operation() as operation, pytest.raises(CalculationRevisionNotFoundError):
        build_modelo_work_review(
            unit.bucket_id,
            unit.modelo,
            unit.filing_year,
            unit.period,
            operation=operation,
            work_unit_repository=work_repo,
            calculation_repository=calculation_repo,
            verification_repository=verification_repo,
            calculation_catalogue=CalculationRevisionCatalogue(),
        )


def test_review_projects_resolvable_work_without_a_calculation_from_real_storage(repos: Repos) -> None:
    work_repo, calculation_repo, _, verification_repo, _ = repos
    work_unit = _persist_work_unit(repos)
    authority = published_authority_operation()

    with bundled_indexed_authority().operation() as operation:
        review = build_modelo_work_review(
            work_unit.bucket_id,
            work_unit.modelo,
            work_unit.filing_year,
            work_unit.period,
            operation=operation,
            work_unit_repository=work_repo,
            calculation_repository=calculation_repo,
            verification_repository=verification_repo,
        )

    assert isinstance(review, ModeloWorkReview)
    assert (
        review.registry_revision_id
        == authority.snapshot(
            str(work_unit.modelo),
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        ).revision.id
    )
    assert review.registry_revision_id == work_unit.revision_id
    assert review.calculation_revision_id is None
    assert review.lifecycle_state is None
    assert review.verification_outcome is None
    assert review.progress.state is ModeloWorkProgressState.IN_PROGRESS
    assert review.progress.materialised_count == 0
    manifest = authority.snapshot(
        str(work_unit.modelo),
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    ).revision.completeness_manifest
    assert manifest is not None
    assert review.progress.target_count == len(manifest.casillas)
    assert review.progress.denominator is not None
    assert review.progress.denominator.registry_revision_id == review.registry_revision_id
    assert review.progress.denominator.source_ref == "aeat-dr-130-2019-v12"
    assert review.findings == ()
    assert review.blockers == ()
    assert review.casillas
    assert all(row.realised_kind is ModeloValueKind.EMPTY and row.value is None for row in review.casillas)
    computed = next(row for row in review.casillas if row.casilla_id == M130_NET_RESULT_CASILLA)
    assert computed.declared_input_kind is InputKind.COMPUTED
    assert computed.origin_anomaly is ModeloWorkOriginAnomaly.BROKEN_CALCULATION_CHAIN


def test_work_review_refuses_a_persisted_revision_with_divergent_registry_coordinate(repos: Repos) -> None:
    """The operator review surface cannot render registry-interpreted stale values."""
    _, calculation_repo, _, _, _ = repos
    work_unit = _persist_work_unit(repos)
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    stale = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=work_unit.modelo,
            revision_id="persisted-stale-revision",
            modelo_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        ),
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={},
        casilla_values={},
        created_at=T0,
        updated_at=T0,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    with pytest.raises(CalculationRevisionPersistenceError):
        calculation_repo.save(upsert_calculation_revision(calculation_repo.load(), stale))


def test_review_progress_is_undefined_without_a_revision_manifest(repos: Repos) -> None:
    work_repo, calculation_repo, _, verification_repo, _ = repos
    work_unit = _persist_work_unit(
        repos,
        modelo=ModeloCode("189"),
        filing_year=2025,
        period_code="0A",
    )

    with bundled_indexed_authority().operation() as operation:
        review = build_modelo_work_review(
            work_unit.bucket_id,
            work_unit.modelo,
            work_unit.filing_year,
            work_unit.period,
            operation=operation,
            work_unit_repository=work_repo,
            calculation_repository=calculation_repo,
            verification_repository=verification_repo,
        )

    assert review.progress.state is ModeloWorkProgressState.UNDEFINED
    assert review.progress.materialised_count is None
    assert review.progress.target_count is None
    assert review.progress.denominator is None


def test_review_progress_reads_a_persisted_blocking_verdict(repos: Repos) -> None:
    work_repo, calculation_repo, _, verification_repo, _ = repos
    work_unit = _persist_work_unit(repos)
    snapshot = published_authority_operation().snapshot(
        str(work_unit.modelo),
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )
    manifest = snapshot.revision.completeness_manifest
    assert manifest is not None
    target = manifest.casillas[0]
    target_definition = next(casilla for casilla in snapshot.revision.casillas if casilla.id == target.casilla_id)
    target_value = Decimal("1")
    casilla_values = {target.casilla_id: target_value}
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=casilla_values,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=work_unit.modelo,
            revision_id=work_unit.revision_id,
            modelo_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        ),
        state=CalculationRevisionState.BORRADOR,
        casilla_values=casilla_values,
        observations=(
            CasillaObservation(
                casilla_id=target.casilla_id,
                value=target_value,
                legal_refs=tuple(target_definition.legal_refs),
                source_refs=tuple(target_definition.source_refs),
            ),
        ),
        created_at=T0,
        updated_at=T0,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    calculation_repo.save(upsert_calculation_revision(calculation_repo.load(), revision))
    work_repo.save(
        upsert_work_unit(
            work_repo.load(),
            work_unit.model_copy(update={"current_calculation_revision_id": revision_id}),
        ),
    )
    finding = ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        casilla_id=target.casilla_id,
        message_locale_key="application.modelo.findings.blocking_rule",
        message_facts={"casilla_id": str(target.casilla_id)},
        legal_refs=tuple(manifest.legal_refs),
        source_refs=tuple(manifest.source_refs),
    )
    report_id = derive_verification_report_id(
        calculation_revision_id=revision_id,
        completeness_status=VerificationCompletenessStatus.BLOCKED,
        findings=(finding,),
        verified_by="operator-A",
    )
    report = VerificationReport(
        verification_report_id=report_id,
        calculation_revision_id=revision_id,
        registry_snapshot_ref=revision.registry_snapshot_ref,
        completeness_status=VerificationCompletenessStatus.BLOCKED,
        findings=(finding,),
        run_at=T0,
        verified_by="operator-A",
        granted_verificado_completo=False,
    )
    verification_repo.save(upsert_verification_report(verification_repo.load(), report))

    with bundled_indexed_authority().operation() as operation:
        review = build_modelo_work_review(
            work_unit.bucket_id,
            work_unit.modelo,
            work_unit.filing_year,
            work_unit.period,
            operation=operation,
            work_unit_repository=work_repo,
            calculation_repository=calculation_repo,
            verification_repository=verification_repo,
        )

    assert review.progress.state is ModeloWorkProgressState.BLOCKED
    assert review.progress.materialised_count == 1
    assert review.progress.target_count == len(manifest.casillas)


def test_review_progress_schema_refuses_unnamed_or_impossible_counts() -> None:
    denominator = ModeloWorkProgressDenominator(
        registry_revision_id="2019-y-siguientes",
        source_ref="aeat-dr-130-2019-v12",
    )
    with pytest.raises(ValidationError, match="undefined modelo work progress"):
        ModeloWorkProgress(
            state=ModeloWorkProgressState.UNDEFINED,
            materialised_count=0,
            target_count=1,
            denominator=denominator,
        )
    with pytest.raises(ValidationError, match="cannot exceed"):
        ModeloWorkProgress(
            state=ModeloWorkProgressState.IN_PROGRESS,
            materialised_count=2,
            target_count=1,
            denominator=denominator,
        )


def test_review_progress_fields_do_not_express_a_ratio() -> None:
    forbidden = ("percent", "percentage", "fraction", "ratio", "pct", "coverage_rate", "completeness")
    schema = ModeloWorkReview.model_json_schema()
    pending: list[object] = [schema]
    names: list[str] = []
    while pending:
        node = pending.pop()
        if isinstance(node, dict):
            properties = node.get("properties")
            if isinstance(properties, dict):
                names.extend(str(name) for name in properties)
            pending.extend(node.values())
        elif isinstance(node, list):
            pending.extend(node)
    joined_names = " ".join(names).casefold()
    assert all(token not in joined_names for token in forbidden)
    assert all(field.annotation is not float for field in ModeloWorkProgress.model_fields.values())


def _calculated_m130(repos: Repos) -> tuple[WorkUnit, CalculationRevision]:
    """Persist one Modelo 130 work unit and calculate it through the real action."""
    work_repo, calculation_repo, _, _, bucket_event_repo = repos
    work_unit = _persist_work_unit(repos)
    profile = load_test_profile_record(_BUCKET_ID)
    replace_test_profile_record(
        profile.model_copy(
            update={
                "facts": (
                    *profile.facts,
                    UserProfileFact(path="iva.m303_regime_composition", value="general"),
                    UserProfileFact(path="iva.redeme_enrolled", value=False),
                    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                    UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                    UserProfileFact(
                        path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled",
                        value=False,
                    ),
                ),
            },
        ),
    )
    with calculation_ports_for_test(
        bucket_id=work_unit.bucket_id,
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        bucket_event_repository=bucket_event_repo,
    ) as ports:
        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            casilla_inputs=DEFAULT_130_BASELINE_INPUTS,
            binding_values={**DEFAULT_130_BINDING_VALUES, _M130_INCOME_BINDING: Decimal("9000")},
            ports=ports,
        )
    return work_unit, revision


def test_graded_admission_carries_the_canonical_review_of_a_calculated_unit(repos: Repos) -> None:
    work_repo, calculation_repo, _, verification_repo, bucket_event_repo = repos
    work_unit, revision = _calculated_m130(repos)
    stored_unit = work_repo.load().work_units[work_unit.work_unit_id]

    with (
        calculation_ports_for_test(
            bucket_id=work_unit.bucket_id,
            work_unit_repository=work_repo,
            calculation_repository=calculation_repo,
            bucket_event_repository=bucket_event_repo,
        ) as ports,
        bundled_indexed_authority().operation() as operation,
    ):
        result = resolve_graded_snapshot_result(
            ModeloWorkspaceExactWorkUnitTargetV1(
                target=ModeloExactWorkUnitTarget(work_unit_id=stored_unit.work_unit_id, bucket_id=stored_unit.bucket_id)
            ),
            required_grade=RegistryAuthorityGrade.CALCULATION,
            bucket_id=stored_unit.bucket_id,
            catalogue_repository=work_repo,
            calculation_ports=ports,
            verification_repository=verification_repo,
            readiness_read_ports=build_state_projection_read_ports(
                operation=operation,
                objects=secure_object_repository_for_bucket(stored_unit.bucket_id),
                bucket_id=stored_unit.bucket_id,
            ),
            operation=operation,
            output_language=OutputLanguage.EN,
        )
        expected_review = build_modelo_work_review(
            work_unit.bucket_id,
            work_unit.modelo,
            work_unit.filing_year,
            work_unit.period,
            operation=operation,
            work_unit_repository=work_repo,
            calculation_repository=calculation_repo,
            verification_repository=verification_repo,
        )

    assert isinstance(result, ModeloWorkspaceGradedSnapshotResultV1)
    projection = result.projection
    assert projection.work_review.disposition is ModeloWorkspaceCapabilityDisposition.AVAILABLE
    assert projection.work_review.review is not None
    assert projection.work_review.review == expected_review
    assert projection.work_review.review.calculation_revision_id == revision.calculation_revision_id
    assert {contributor.owner for contributor in projection.contributors} >= {
        MODELO_WORKSPACE_BOUNDED_REVIEW_PRODUCER_CONTRACT_V1.contributor.owner
    }
    assert len(projection.contributors) == len(ModeloWorkspaceContributorKindV1)
    computed = {
        str(row.casilla_id) for row in projection.work_review.review.casillas if row.concrete_formula is not None
    }
    assert str(M130_NET_RESULT_CASILLA) in computed
    verification = next(
        capability
        for capability in projection.capabilities
        if capability.capability is ModeloWorkspaceCapabilityName.VERIFICATION_READINESS
    )
    bounded_review = MODELO_WORKSPACE_BOUNDED_REVIEW_PRODUCER_CONTRACT_V1.contributor
    assert (verification.producer_owner, verification.producer) == (bounded_review.owner, bounded_review.producer)
    assert verification.disposition is ModeloWorkspaceCapabilityDisposition.UNMEASURED


def test_review_joins_real_persisted_calculation_into_origin_layers(repos: Repos) -> None:
    work_repo, calculation_repo, filing_repo, verification_repo, bucket_event_repo = repos
    work_unit = _persist_work_unit(repos)
    profile = load_test_profile_record(_BUCKET_ID)
    replace_test_profile_record(
        profile.model_copy(
            update={
                "facts": (
                    *profile.facts,
                    UserProfileFact(path="iva.m303_regime_composition", value="general"),
                    UserProfileFact(path="iva.redeme_enrolled", value=False),
                    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                    UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                    UserProfileFact(
                        path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled",
                        value=False,
                    ),
                ),
            },
        ),
    )
    with calculation_ports_for_test(
        bucket_id=work_unit.bucket_id,
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        bucket_event_repository=bucket_event_repo,
    ) as _calculation_ports_413:
        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            casilla_inputs=DEFAULT_130_BASELINE_INPUTS,
            binding_values={**DEFAULT_130_BINDING_VALUES, _M130_INCOME_BINDING: Decimal("9000")},
            ports=_calculation_ports_413,
        )

    with bundled_indexed_authority().operation() as operation:
        review = build_modelo_work_review(
            work_unit.bucket_id,
            work_unit.modelo,
            work_unit.filing_year,
            work_unit.period,
            operation=operation,
            work_unit_repository=work_repo,
            calculation_repository=calculation_repo,
            verification_repository=verification_repo,
        )
    rows = {row.casilla_id: row for row in review.casillas}

    assert review.calculation_revision_id == revision.calculation_revision_id
    assert review.lifecycle_state is revision.state
    assert rows[M130_INCOME_CASILLA].realised_kind is ModeloValueKind.LITERAL
    assert rows[M130_INCOME_CASILLA].value == Decimal("10000")
    assert rows[M130_INCOME_CASILLA].origin_anomaly is ModeloWorkOriginAnomaly.OPERATOR_OVERRIDE
    assert rows[M130_INCOME_CASILLA].concrete_bindings
    assert rows[M130_INCOME_CASILLA].concrete_bindings[0].resolved is True
    assert rows[M130_NET_RESULT_CASILLA].realised_kind is ModeloValueKind.COMPUTED
    assert rows[M130_NET_RESULT_CASILLA].value == Decimal("7000")
    assert rows[M130_NET_RESULT_CASILLA].origin_anomaly is None
    assert rows[M130_CARRY_FORWARD_CASILLA].realised_kind is ModeloValueKind.COMPUTED
    carry_forward_formula = rows[M130_CARRY_FORWARD_CASILLA].concrete_formula
    assert carry_forward_formula is not None
    assert "modelo-130-resultados-negativos-anteriores" in carry_forward_formula.operand_refs
    with calculation_ports_for_test(
        bucket_id=work_unit.bucket_id,
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        bucket_event_repository=bucket_event_repo,
    ) as _calculation_ports_453:
        equal_value_revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            casilla_inputs=DEFAULT_130_BASELINE_INPUTS,
            binding_values={**DEFAULT_130_BINDING_VALUES, _M130_INCOME_BINDING: Decimal("10000")},
            ports=_calculation_ports_453,
        )
    with bundled_indexed_authority().operation() as operation:
        equal_value_review = build_modelo_work_review(
            work_unit.bucket_id,
            work_unit.modelo,
            work_unit.filing_year,
            work_unit.period,
            operation=operation,
            work_unit_repository=work_repo,
            calculation_repository=calculation_repo,
            verification_repository=verification_repo,
        )
    equal_value_income = next(row for row in equal_value_review.casillas if row.casilla_id == M130_INCOME_CASILLA)
    assert equal_value_review.calculation_revision_id == equal_value_revision.calculation_revision_id
    assert equal_value_income.realised_kind is ModeloValueKind.INHERITED
    assert equal_value_income.origin_anomaly is None
    assert equal_value_income.concrete_bindings[0].resolved is True

    verification = verify_revision(
        equal_value_revision.calculation_revision_id,
        revision=equal_value_revision,
        work_unit=work_unit,
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        verification_repository=verification_repo,
        filing_repository=filing_repo,
        bucket_event_repository=bucket_event_repo,
        clock=equal_value_revision.updated_at,
    )
    with bundled_indexed_authority().operation() as operation:
        verified_review = build_modelo_work_review(
            work_unit.bucket_id,
            work_unit.modelo,
            work_unit.filing_year,
            work_unit.period,
            operation=operation,
            work_unit_repository=work_repo,
            calculation_repository=calculation_repo,
            verification_repository=verification_repo,
        )
    assert verification.completeness_status is VerificationCompletenessStatus.COMPLETE
    assert verified_review.progress.state is ModeloWorkProgressState.COMPLETE
    assert verified_review.progress.materialised_count == verified_review.progress.target_count


def test_real_review_projects_only_fingerprint_for_persisted_row_identity(repos: Repos) -> None:
    work_repo, calculation_repo, _, verification_repo, bucket_event_repo = repos
    work_unit = _persist_work_unit(repos)
    with calculation_ports_for_test(
        bucket_id=work_unit.bucket_id,
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        bucket_event_repository=bucket_event_repo,
    ) as _calculation_ports_511:
        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            casilla_inputs=DEFAULT_130_BASELINE_INPUTS,
            binding_values=DEFAULT_130_BINDING_VALUES,
            ports=_calculation_ports_511,
        )
    raw_identity = "opaque-review-row-canary"
    fingerprint = "d" * 64
    amended = revision.model_copy(
        update={
            "row_binding_values": {"review-row-binding": {"1": "100"}},
            "row_source_identities": {
                ("review-row-binding", 1): RowSourceIdentity(
                    source_kind=BindingSourceKind.INVENTORY,
                    source_row_identity=raw_identity,
                    fingerprint=fingerprint,
                ),
            },
        },
    )
    amended = amended.model_copy(
        update={"calculation_revision_id": derive_calculation_revision_id_from_revision(amended)},
    )
    calculation_repo.save(upsert_calculation_revision(calculation_repo.load(), amended))
    stored_work = work_repo.load().get(work_unit.work_unit_id)
    assert stored_work is not None
    work_repo.save(
        upsert_work_unit(
            work_repo.load(),
            stored_work.model_copy(update={"current_calculation_revision_id": amended.calculation_revision_id}),
        ),
    )

    with bundled_indexed_authority().operation() as operation:
        review = build_modelo_work_review(
            work_unit.bucket_id,
            work_unit.modelo,
            work_unit.filing_year,
            work_unit.period,
            operation=operation,
            work_unit_repository=work_repo,
            calculation_repository=calculation_repo,
            verification_repository=verification_repo,
        )

    assert [item.model_dump(mode="json") for item in review.row_source_fingerprints] == [
        {
            "binding_id": "review-row-binding",
            "row_index": 1,
            "source_kind": "inventory",
            "fingerprint": fingerprint,
        },
    ]
    rendered = f"{review!r} {review.model_dump()!r} {review.model_dump_json()}"
    assert raw_identity not in rendered


def test_review_reads_persisted_date_bindings_without_decimal_reinterpretation(repos: Repos) -> None:
    work_repo, calculation_repo, _, verification_repo, _ = repos
    work_unit = _persist_work_unit(
        repos,
        modelo=ModeloCode("100"),
        filing_year=2025,
        period_code="0A",
    )
    snapshot = published_authority_operation().snapshot(
        str(work_unit.modelo),
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )
    date_binding_id = next(iter(sorted(revision_date_binding_ids(snapshot.revision))))
    binding_overrides = {date_binding_id: "1980-01-01"}
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides=binding_overrides,
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=work_unit.modelo,
            revision_id=work_unit.revision_id,
            modelo_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        ),
        state=CalculationRevisionState.BORRADOR,
        binding_overrides=binding_overrides,
        created_at=T0,
        updated_at=T0,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    calculation_repo.save(upsert_calculation_revision(calculation_repo.load(), revision))
    work_repo.save(
        upsert_work_unit(
            work_repo.load(),
            work_unit.model_copy(update={"current_calculation_revision_id": revision_id}),
        ),
    )

    with bundled_indexed_authority().operation() as operation:
        review = build_modelo_work_review(
            work_unit.bucket_id,
            work_unit.modelo,
            work_unit.filing_year,
            work_unit.period,
            operation=operation,
            work_unit_repository=work_repo,
            calculation_repository=calculation_repo,
            verification_repository=verification_repo,
        )

    assert review.calculation_revision_id == revision_id
