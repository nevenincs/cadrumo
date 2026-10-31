"""Assert Modelo and IVA wallet operation outcomes for the registered executor conformance run."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from zipfile import ZipFile

from cadrumo.adapters.persistence.storage.attachment import AttachmentStore

from ...adapters.persistence.profile.calculation_observations import IvaWalletDecisionRepository
from ...adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...adapters.persistence.profile.tests.cross_period_seeding import SEEDED_SOURCE_TAX_ID
from ...application.aggregation.service import aggregate_per_modelo
from ...application.live.iva_wallet_history_operation import (
    IVA_WALLET_HISTORY_OPERATION_DEFINITION_ID,
    IvaWalletHistoryProjection,
    IvaWalletHistoryRequest,
)
from ...application.modelo.aggregate_projection import ModeloAggregateProjection
from ...application.modelo.calculation_report_verification_operation import (
    MODELO_CALCULATION_REPORT_VERIFY_OPERATION_DEFINITION_ID,
    ModeloCalculationReportVerificationProjection,
)
from ...application.modelo.dependency_operation import (
    MODELO_DEPENDENCY_OPERATION_DEFINITION_ID,
    ModeloDependencyProjection,
    ModeloDependencyRequest,
)
from ...application.modelo.history_operation import ModeloWorkHistoryProjection, ModeloWorkHistoryRequest
from ...application.modelo.iva_wallet_balance_operation import ModeloIvaWalletBalanceProjection
from ...application.modelo.iva_wallet_correction_operation import (
    MODELO_IVA_WALLET_CORRECTION_OPERATION_DEFINITION_ID,
    ModeloIvaWalletCorrectionProjection,
)
from ...application.modelo.iva_wallet_override_operation import ModeloIvaWalletOverrideProjection
from ...application.modelo.iva_wallet_seed_operation import ModeloIvaWalletSeedProjection
from ...application.modelo.m303_attestation_operation import (
    ModeloWorkM303AttestationPublicResultV2,
    ModeloWorkM303AttestationRequest,
)
from ...application.modelo.review_package_operation import (
    ModeloReviewPackageBuildPublicResultV1,
    ModeloReviewPackageBuildRequest,
)
from ...application.modelo.revision_inventory_operation import ModeloWorkRevisionsProjection, ModeloWorkRevisionsRequest
from ...application.modelo.revision_snapshot_operation import ModeloWorkRevisionSnapshotRequest
from ...application.modelo.taxation_comparison_operation import (
    MODELO_TAXATION_COMPARISON_OPERATION_DEFINITION_ID,
    ModeloTaxationComparisonRequest,
)
from ...application.modelo.wizard_attempt_operation import (
    ModeloWorkWizardAttemptCalculated,
    ModeloWorkWizardAttemptProjection,
    ModeloWorkWizardAttemptRequest,
)
from ...application.modelo.wizard_context_operation import (
    ModeloWorkWizardContextProjection,
    ModeloWorkWizardContextRequest,
)
from ...application.modelo.work_create_operation import (
    ModeloWorkCreateProjection,
    ModeloWorkCreateRefusal,
    ModeloWorkCreateRequest,
)
from ...application.modelo.work_inventory_operation import ModeloWorkListProjection, ModeloWorkListRequest
from ...application.modelo.work_review_contracts import ModeloWorkReviewProjection, ModeloWorkReviewRequest
from ...application.operations.public_period import PublicPeriod
from ...core.external_constants import OutputLanguage
from ...core.iva_compensation_provenance import IvaCompensationStateProvenance
from ...core.period import Period
from ...domain.attachments.m303_filing_evidence import (
    M303Exonerado390ApplicabilityAssertion,
    parse_m303_exonerado_390_applicability_attestation,
)
from ...domain.modelos.work_unit import WorkUnitState
from . import modelo_operation_test_support
from .aggregate_operation_test_support import aggregate_conformance_command
from .registered_executor_outcome_context import ExecutorOutcome
from .registered_executor_result_assertions import (
    _assert_calculation_report_verification_projection,
)


def assert_modelo_aggregate_outcome(ctx: ExecutorOutcome) -> None:
    """Check the modelo.aggregate public result and effects."""
    aggregate_result = ctx.resolve(ModeloAggregateProjection)
    assert isinstance(aggregate_result, ModeloAggregateProjection)
    canonical_aggregate = aggregate_per_modelo(
        aggregate_conformance_command(operation=ctx.operation), operation=ctx.operation
    )
    assert canonical_aggregate.log_fields.observation_count == 2
    assert canonical_aggregate.log_fields.result_row_count == 1
    assert aggregate_result == ModeloAggregateProjection(
        outcome="aggregated",
        profile_id=ctx.profile_id,
        modelo=str(canonical_aggregate.modelo),
        period=PublicPeriod.from_period(canonical_aggregate.period),
        provider=canonical_aggregate.provider,
        observation_count=canonical_aggregate.log_fields.observation_count,
        source_kinds=canonical_aggregate.source_kinds,
        result_row_count=canonical_aggregate.log_fields.result_row_count,
        clave_breakdown=(),
        absent_source_families=(),
        withholding_window=None,
        refusal_reason=None,
    )


def assert_modelo_work_create_outcome(ctx: ExecutorOutcome) -> None:
    """Check the modelo.work.create public result and effects."""
    assert isinstance(ctx.payload, ModeloWorkCreateRequest)
    assert ctx.observed.projection.result_ref is None
    result = ctx.resolve(ModeloWorkCreateProjection)
    assert isinstance(result, ModeloWorkCreateProjection)
    assert result.profile_id == ctx.profile_id
    assert result.period == ctx.payload.period
    assert isinstance(result.outcome, ModeloWorkCreateRefusal)
    assert result.outcome.modelo == ctx.payload.modelo == "202"
    assert result.outcome.reason
    assert WorkUnitCatalogueRepository().load().work_units == {}


def assert_modelo_dependency_outcome(ctx: ExecutorOutcome) -> None:
    """Check the MODELO_DEPENDENCY_OPERATION_DEFINITION_ID public result and effects."""
    assert isinstance(ctx.payload, ModeloDependencyRequest)
    result = ctx.resolve(ModeloDependencyProjection)
    assert isinstance(result, ModeloDependencyProjection)
    assert result.profile_id == ctx.profile_id
    assert result.snapshot.filing_year == ctx.payload.filing_year
    assert result.snapshot.modelo_filter == ctx.payload.modelo
    assert result.snapshot.period_filter == ctx.payload.period
    assert result.snapshot.clean_state is not None
    assert result.snapshot.clean_state.target_modelo == ctx.payload.modelo
    assert result.snapshot.clean_state.target_period == ctx.payload.period
    assert all(item.target_filing_year == ctx.payload.filing_year for item in result.snapshot.items)


def assert_modelo_work_revision_snapshot_outcome(ctx: ExecutorOutcome) -> None:
    """Check the modelo.work.revision_snapshot public result and effects."""
    assert isinstance(ctx.payload, ModeloWorkRevisionSnapshotRequest)
    assert ctx.observed.projection.result_ref is not None
    assert ctx.observed.projection.result_ref != ctx.payload.calculation_revision_id


def assert_modelo_taxation_comparison_outcome(ctx: ExecutorOutcome) -> None:
    """Check the MODELO_TAXATION_COMPARISON_OPERATION_DEFINITION_ID public result and effects."""
    assert isinstance(ctx.payload, ModeloTaxationComparisonRequest)
    assert ctx.observed.projection.result_ref is None
    assert WorkUnitCatalogueRepository().load().get(ctx.payload.work_unit_id) is not None


def assert_modelo_work_list_outcome(ctx: ExecutorOutcome) -> None:
    """Check the modelo.work.list public result and effects."""
    assert isinstance(ctx.payload, ModeloWorkListRequest)
    inventory = ctx.resolve(ModeloWorkListProjection)
    assert isinstance(inventory, ModeloWorkListProjection)
    assert inventory.profile_id == ctx.profile_id
    assert inventory.include_discarded is False
    assert len(inventory.units) == 1
    row = inventory.units[0]
    assert row.bucket_id == str(ctx.profile_id)
    assert row.modelo == "130"
    assert row.filing_year == 2025
    assert row.state is WorkUnitState.BORRADOR


def assert_modelo_work_history_outcome(ctx: ExecutorOutcome) -> None:
    """Check the modelo.work.history public result and effects."""
    assert isinstance(ctx.payload, ModeloWorkHistoryRequest)
    history = ctx.resolve(ModeloWorkHistoryProjection)
    assert isinstance(history, ModeloWorkHistoryProjection)
    assert history.profile_id == ctx.profile_id
    assert history.history.bucket_id == str(ctx.profile_id)
    assert history.history.work_unit_id == ctx.payload.work_unit_id
    assert history.history.events
    assert all(event.bucket_id == ctx.profile_id for event in history.history.events)


def assert_modelo_work_review_outcome(ctx: ExecutorOutcome) -> None:
    """Check the modelo.work.review public result and effects."""
    assert isinstance(ctx.payload, ModeloWorkReviewRequest)
    review = ctx.resolve(ModeloWorkReviewProjection)
    assert isinstance(review, ModeloWorkReviewProjection)
    assert review.profile_id == ctx.profile_id
    assert review.review.bucket_id == str(ctx.profile_id)
    assert review.review.work_unit_id == ctx.payload.work_unit_id
    assert review.review.modelo == modelo_operation_test_support.MODELO
    assert review.review.filing_year == modelo_operation_test_support.MODELO_FILING_YEAR
    assert review.review.period == PublicPeriod.from_period(
        Period.from_year_and_code(
            modelo_operation_test_support.MODELO_FILING_YEAR, modelo_operation_test_support.MODELO_PERIOD
        )
    )
    assert review.review.calculation_revision_id is None
    assert review.review.lifecycle_state is None
    assert review.review.verification_outcome is None


def assert_modelo_work_wizard_context_outcome(ctx: ExecutorOutcome) -> None:
    """Check the modelo.work.wizard_context public result and effects."""
    assert isinstance(ctx.payload, ModeloWorkWizardContextRequest)
    context = ctx.resolve(ModeloWorkWizardContextProjection)
    assert isinstance(context, ModeloWorkWizardContextProjection)
    assert context.profile_id == ctx.profile_id
    assert context.unit.work_unit_id == ctx.payload.work_unit_id
    assert context.unit.bucket_id == str(ctx.profile_id)
    assert context.output_language is OutputLanguage.ES
    assert context.steps
    assert all(step.legal_refs and step.source_refs for step in context.steps)


def assert_modelo_work_wizard_attempt_outcome(ctx: ExecutorOutcome) -> None:
    """Check the modelo.work.wizard_attempt public result and effects."""
    assert isinstance(ctx.payload, ModeloWorkWizardAttemptRequest)
    attempt = ctx.resolve(ModeloWorkWizardAttemptProjection)
    assert isinstance(attempt, ModeloWorkWizardAttemptProjection)
    assert attempt.profile_id == ctx.profile_id
    assert attempt.output_language is OutputLanguage.ES
    assert isinstance(attempt.outcome, ModeloWorkWizardAttemptCalculated)
    calculation_result = attempt.outcome.result
    assert calculation_result.revision_published is True
    assert calculation_result.work_unit_id == ctx.payload.calculation.work_unit_id
    assert calculation_result.unit.current_calculation_revision_id == calculation_result.calculation_revision_id
    calculation_catalogue = CalculationRevisionCatalogueRepository().load(operation=ctx.operation)
    revision = calculation_catalogue.get(calculation_result.calculation_revision_id)
    assert revision is not None
    assert revision.work_unit_id == ctx.payload.calculation.work_unit_id
    assert revision.calculation_revision_id == calculation_result.calculation_revision_id
    unit = WorkUnitCatalogueRepository().load().get(ctx.payload.calculation.work_unit_id)
    assert unit is not None
    assert unit.current_calculation_revision_id == revision.calculation_revision_id


def assert_modelo_work_revisions_outcome(ctx: ExecutorOutcome) -> None:
    """Check the modelo.work.revisions public result and effects."""
    assert isinstance(ctx.payload, ModeloWorkRevisionsRequest)
    inventory = ctx.resolve(ModeloWorkRevisionsProjection)
    assert isinstance(inventory, ModeloWorkRevisionsProjection)
    stored_revisions = CalculationRevisionCatalogueRepository().load().revisions
    assert inventory.profile_id == ctx.profile_id
    assert inventory.work_unit_id_filter is None
    assert {row.calculation_revision_id for row in inventory.revisions} == set(stored_revisions)
    assert len(inventory.revisions) == len(stored_revisions)


def assert_modelo_calculation_report_verify_outcome(ctx: ExecutorOutcome) -> None:
    """Check the MODELO_CALCULATION_REPORT_VERIFY_OPERATION_DEFINITION_ID public result and effects."""
    verification = ctx.resolve(ModeloCalculationReportVerificationProjection)
    _assert_calculation_report_verification_projection(ctx.payload, verification, profile_id=ctx.profile_id)


def assert_modelo_review_package_build_outcome(ctx: ExecutorOutcome) -> None:
    """Check the modelo.review_package.build public result and effects."""
    assert isinstance(ctx.payload, ModeloReviewPackageBuildRequest)
    result = ctx.resolve(ModeloReviewPackageBuildPublicResultV1)
    assert isinstance(result, ModeloReviewPackageBuildPublicResultV1)
    package_path = Path(result.output_path)
    assert package_path == Path(ctx.payload.output_path)
    assert package_path.is_file()
    expected_revision = CalculationRevisionCatalogueRepository().load().get(ctx.payload.calculation_revision_id)
    assert expected_revision is not None
    assert result.manifest.bucket_id == str(ctx.profile_id)
    assert result.manifest.work_unit_id == expected_revision.work_unit_id
    assert result.manifest.calculation_revision_id == ctx.payload.calculation_revision_id
    assert result.member_count >= 1
    assert result.handoff_required is True
    with ZipFile(package_path) as package:
        assert package.testzip() is None


def assert_modelo_work_m303_attestation_outcome(ctx: ExecutorOutcome) -> None:
    """Check the modelo.work.m303_attestation public result and effects."""
    assert isinstance(ctx.payload, ModeloWorkM303AttestationRequest)
    result = ctx.resolve(ModeloWorkM303AttestationPublicResultV2)
    assert isinstance(result, ModeloWorkM303AttestationPublicResultV2)
    assert result.profile_id == ctx.profile_id
    assert result.work_unit_id is None
    assert result.period == PublicPeriod.from_period(Period.from_year_and_code(2025, "4T"))
    evidence = parse_m303_exonerado_390_applicability_attestation(AttachmentStore().read_bytes(result.attachment_id))
    assert evidence.period == Period.from_year_and_code(2025, "4T")
    assert evidence.asserted_value is M303Exonerado390ApplicabilityAssertion.NOT_APPLICABLE
    assert not WorkUnitCatalogueRepository().load().work_units


def assert_iva_wallet_history_outcome(ctx: ExecutorOutcome) -> None:
    """Check the IVA_WALLET_HISTORY_OPERATION_DEFINITION_ID public result and effects."""
    assert isinstance(ctx.payload, IvaWalletHistoryRequest)
    history = ctx.resolve(IvaWalletHistoryProjection)
    assert isinstance(history, IvaWalletHistoryProjection)
    assert history.profile_id == ctx.profile_id
    assert history.as_of_year == ctx.payload.as_of_year
    assert history.row_count == 1
    row = history.rows[0]
    assert row.year == 2025
    assert row.period.to_period() == Period.from_year_and_code(2025, "1T")
    assert row.provenance is IvaCompensationStateProvenance.APP_FILING
    assert row.generated_amount == "40.00"
    assert history.carry_forward_lot_count == 1
    assert history.carry_forward_lots[0].source_period == row.period
    assert history.carry_forward_lots[0].remaining_amount == "40.00"
    assert history.authority_decision_count == 0
    assert ctx.iva_history_before is not None
    assert IvaCompensationHistoryRepository().list_periods() == ctx.iva_history_before


def assert_modelo_iva_wallet_correction_outcome(ctx: ExecutorOutcome) -> None:
    """Check the MODELO_IVA_WALLET_CORRECTION_OPERATION_DEFINITION_ID public result and effects."""
    correction = ctx.resolve(ModeloIvaWalletCorrectionProjection)
    assert isinstance(correction, ModeloIvaWalletCorrectionProjection)
    assert correction.profile_id == ctx.profile_id
    assert correction.period.to_period() == Period.from_year_and_code(2024, "4T")
    assert correction.previous_amount == "500.00"
    assert correction.amount == "1200.50"
    assert correction.provenance is IvaCompensationStateProvenance.OPERATOR_CORRECTION
    assert correction.register_status is None
    assert correction.reason == "corrected opening balance"
    persisted = IvaCompensationHistoryRepository(bucket_id=str(ctx.profile_id)).load_period(
        correction.period.to_period()
    )
    assert persisted is not None
    assert persisted.available_end_amount == Decimal("1200.50")


def assert_modelo_iva_wallet_balance_outcome(ctx: ExecutorOutcome) -> None:
    """Check the modelo.iva-wallet.balance public result and effects."""
    balance = ctx.resolve(ModeloIvaWalletBalanceProjection)
    assert isinstance(balance, ModeloIvaWalletBalanceProjection)
    assert balance.profile_id == ctx.profile_id
    assert balance.as_of_year == 2024
    assert Decimal(balance.total_balance) == Decimal("500.00")
    assert Decimal(balance.active_balance) == Decimal("500.00")
    assert Decimal(balance.expired_balance) == Decimal("0.00")
    assert Decimal(balance.unallocated_applied_amount) == Decimal("0.00")
    assert balance.lot_count == 1
    assert balance.next_expiry_year == 2028


def assert_modelo_iva_wallet_seed_outcome(ctx: ExecutorOutcome) -> None:
    """Check the modelo.iva-wallet.seed public result and effects."""
    seeded = ctx.resolve(ModeloIvaWalletSeedProjection)
    assert isinstance(seeded, ModeloIvaWalletSeedProjection)
    assert seeded.profile_id == ctx.profile_id
    assert seeded.period.to_period() == Period.from_year_and_code(2024, "4T")
    assert seeded.amount == "500.00"
    assert seeded.provenance is IvaCompensationStateProvenance.OPERATOR_SEED
    persisted_seed = IvaCompensationHistoryRepository(bucket_id=str(ctx.profile_id)).load_period(
        seeded.period.to_period()
    )
    assert persisted_seed is not None
    assert persisted_seed.available_end_amount == Decimal("500.00")


def assert_modelo_iva_wallet_override_outcome(ctx: ExecutorOutcome) -> None:
    """Check the modelo.iva-wallet.override public result and effects."""
    overridden = ctx.resolve(ModeloIvaWalletOverrideProjection)
    assert isinstance(overridden, ModeloIvaWalletOverrideProjection)
    assert overridden.profile_id == ctx.profile_id
    assert overridden.period.to_period() == Period.from_year_and_code(2025, "1T")
    assert overridden.amount == "450.00"
    assert overridden.reason == "operator asserted prior compensation"
    assert overridden.evidence_locator == "synthetic:conformance:prior-compensation"
    assert str(overridden.selected_authority) == "taxpayer_override"
    assert str(overridden.divergence) == "override"
    persisted_override = IvaWalletDecisionRepository().load_decision(
        SEEDED_SOURCE_TAX_ID, overridden.period.to_period()
    )
    assert persisted_override is not None
    assert str(persisted_override.selected_authority) == "taxpayer_override"


MODELO_OUTCOME_ASSERTIONS: dict[str, Callable[[ExecutorOutcome], None]] = {
    "modelo.aggregate": assert_modelo_aggregate_outcome,
    "modelo.work.create": assert_modelo_work_create_outcome,
    MODELO_DEPENDENCY_OPERATION_DEFINITION_ID: assert_modelo_dependency_outcome,
    "modelo.work.revision_snapshot": assert_modelo_work_revision_snapshot_outcome,
    MODELO_TAXATION_COMPARISON_OPERATION_DEFINITION_ID: assert_modelo_taxation_comparison_outcome,
    "modelo.work.list": assert_modelo_work_list_outcome,
    "modelo.work.history": assert_modelo_work_history_outcome,
    "modelo.work.review": assert_modelo_work_review_outcome,
    "modelo.work.wizard_context": assert_modelo_work_wizard_context_outcome,
    "modelo.work.wizard_attempt": assert_modelo_work_wizard_attempt_outcome,
    "modelo.work.revisions": assert_modelo_work_revisions_outcome,
    MODELO_CALCULATION_REPORT_VERIFY_OPERATION_DEFINITION_ID: assert_modelo_calculation_report_verify_outcome,
    "modelo.review_package.build": assert_modelo_review_package_build_outcome,
    "modelo.work.m303_attestation": assert_modelo_work_m303_attestation_outcome,
    IVA_WALLET_HISTORY_OPERATION_DEFINITION_ID: assert_iva_wallet_history_outcome,
    MODELO_IVA_WALLET_CORRECTION_OPERATION_DEFINITION_ID: assert_modelo_iva_wallet_correction_outcome,
    "modelo.iva-wallet.balance": assert_modelo_iva_wallet_balance_outcome,
    "modelo.iva-wallet.seed": assert_modelo_iva_wallet_seed_outcome,
    "modelo.iva-wallet.override": assert_modelo_iva_wallet_override_outcome,
}
