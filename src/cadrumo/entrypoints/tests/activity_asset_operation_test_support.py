"""Pinned-authority seed helpers for activity-asset executor conformance."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from ...adapters.persistence.storage.tests.profile_capsule_runtime import upsert_test_profile_facts
from ...application.actividad_asset.activity_asset_contracts import (
    ACTIVITY_ASSET_ACQUISITION_CANDIDATES_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_CLAIM_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_CORRECT_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_CREATE_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_DESCRIBE_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_FILING_HANDOFF_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_FORECAST_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_FORM_OPTIONS_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_INSPECT_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_LIST_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_PLAN_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_TIMELINE_OPERATION_DEFINITION_ID,
    ActivityAssetAuthorityProvenance,
    ActivityAssetClaimRequest,
    ActivityAssetCorrectRequest,
    ActivityAssetCreateRequest,
    ActivityAssetDescribeRequest,
    ActivityAssetDisposeRequest,
    ActivityAssetFilingHandoffRequest,
    ActivityAssetForecastRequest,
    ActivityAssetInspectRequest,
)
from ...application.actividad_asset.activity_asset_projections import (
    ActivityAssetAcquisitionCandidatesProjection,
    ActivityAssetClaimProjection,
    ActivityAssetCorrectProjection,
    ActivityAssetCreateProjection,
    ActivityAssetDescribeProjection,
    ActivityAssetDisposalCalculateProjection,
    ActivityAssetDisposeProjection,
    ActivityAssetFilingHandoffProjection,
    ActivityAssetForecastProjection,
    ActivityAssetFormOptionsProjection,
    ActivityAssetInspectProjection,
    ActivityAssetListProjection,
    ActivityAssetPlanProjection,
    ActivityAssetTimelineProjection,
)
from ...application.actividad_asset.history import ActivityAssetHistory
from ...application.actividad_asset.ports import ActivityAssetHistoryRepository as ActivityAssetHistoryPort
from ...application.calculations.actividad_asset_schedule import forecast_activity_asset_charge
from ...application.ledger.models import ManualLedgerTransactionCommand
from ...application.ledger.tests.manual_transaction_support import create_manual_transaction
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.irpf_regimes import irpf_estimation_regime_directa_normal_token
from ...domain.renta.actividad_asset.claims import (
    AmortizationClaim,
    asset_schedule_history,
    project_m100,
)
from ...domain.renta.actividad_asset.election import (
    AcquiredCondition,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    DirectEstimationRegime,
)
from ...domain.renta.actividad_asset.lifecycle import (
    AcquisitionLineageReference,
    AcquisitionShape,
    ActivityAssetBasis,
    ActivityAssetRevision,
    AssetBasisStage,
    AssetKind,
    OpeningAmortizationHistory,
    OpeningHistoryStatus,
)
from ...domain.renta.actividad_asset.schedule import ScheduledAmortizationCharge
from ...domain.transactions.enums import BusinessClassification, TransactionDirection
from ...domain.user_profile.values import UserProfileFact
from ..actividad_asset_composition import build_activity_asset_operation_ports
from ..ledger_action_composition import compose_ledger_action_ports


@dataclass(frozen=True, slots=True)
class ActivityAssetSeed:
    """One canonical asset revision, pinned forecast, and profile repository."""

    repository: ActivityAssetHistoryPort
    revision: ActivityAssetRevision
    forecast: ScheduledAmortizationCharge
    claim: AmortizationClaim | None
    acquisition_transaction_id: str


def seed_acquisition_transaction(profile_id: UUID, *, operation: PinnedAuthorityOperation) -> str:
    """Persist the EUR 300.00 payment an asset revision names as its acquisition; return its ledger id."""
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=str(profile_id),
            booked_date=date(2025, 1, 1),
            amount=Decimal("300.00"),
            direction=TransactionDirection.OUTGOING,
            description="activity-asset conformance acquisition",
            business_classification=BusinessClassification.BUSINESS,
            actor="activity-asset-conformance",
        ),
        ports=compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation),
    )
    return created.ref.transaction_id


def activity_asset_revision(
    asset_id: str,
    *,
    acquisition_transaction_id: str,
    revision_number: int = 1,
    supersedes_revision_id: str | None = None,
) -> ActivityAssetRevision:
    """Build a valid normal-estimation asset revision for the 2025 published table."""
    return ActivityAssetRevision(
        asset_id=asset_id,
        revision_number=revision_number,
        supersedes_revision_id=supersedes_revision_id,
        acquisition=AcquisitionLineageReference(
            observed_transaction_id=acquisition_transaction_id,
            invoice_evidence_id=f"conformance-invoice-{asset_id}",
            evidence_fingerprint="b" * 64,
        ),
        acquisition_shape=AcquisitionShape.PRIMARY_PURCHASE,
        asset_kind=AssetKind.MATERIAL,
        basis=ActivityAssetBasis(
            stage=AssetBasisStage.BUSINESS_ALLOCATED,
            basis_amount=Decimal("300.00"),
            non_deductible_iva=Decimal("0"),
            prior_allocation_provenance="conformance reviewed allocation",
        ),
        in_service_date=date(2025, 1, 1),
        opening_history=OpeningAmortizationHistory(
            status=OpeningHistoryStatus.KNOWN,
            accumulated_amount=Decimal("0"),
        ),
        acquired_condition=AcquiredCondition.NEW,
        amortization=ActivityAssetAmortizationElection(
            regime=DirectEstimationRegime.NORMAL,
            method=AmortizationMethod.LINEAR,
            authority_class_key="equipo-proceso-informacion",
        ),
    )


def seed_activity_asset(
    profile_id: UUID,
    *,
    operation: PinnedAuthorityOperation,
    asset_id: str,
    include_claim: bool = False,
) -> ActivityAssetSeed:
    """Persist one real revision and optionally its forecast-derived claim."""
    upsert_test_profile_facts(
        profile_id,
        (
            UserProfileFact(
                path="irpf.estimation_regime",
                value=str(irpf_estimation_regime_directa_normal_token(authority=operation)),
            ),
        ),
    )
    ports = build_activity_asset_operation_ports(bucket_id=str(profile_id), operation=operation)
    repository = ports.history_repository
    acquisition_transaction_id = seed_acquisition_transaction(profile_id, operation=operation)
    revision = activity_asset_revision(asset_id, acquisition_transaction_id=acquisition_transaction_id)
    history = repository.append_revision(revision)
    forecast = forecast_activity_asset_charge(
        revision,
        modelo_100_revision=operation.revision_for_context("100", filing_year=2025, period="0A"),
        authority_generation=operation.pin().logical_generation,
        covered_from=date(2025, 1, 1),
        covered_until=date(2026, 1, 1),
        history=asset_schedule_history(
            history.claims,
            history.revisions,
            asset_id=asset_id,
            tax_year=2025,
        ),
        taxpayer_workforce=lambda: (),
        legal_reference=operation.legal_reference,
    )
    claim: AmortizationClaim | None = None
    if include_claim:
        claim = AmortizationClaim.from_schedule(
            forecast,
            asset_kind=revision.asset_kind,
            creating_operation="activity-asset-conformance.seed",
        )
        repository.record_claim(claim)
    return ActivityAssetSeed(
        repository=repository,
        revision=revision,
        forecast=forecast,
        claim=claim,
        acquisition_transaction_id=acquisition_transaction_id,
    )


def assert_activity_asset_conformance_result(
    *,
    definition_id: str,
    payload: BaseModel,
    projection: BaseModel,
    before: ActivityAssetHistory,
    after: ActivityAssetHistory,
    operation: PinnedAuthorityOperation,
) -> None:
    """Prove each supervisor result against its pinned authority and canonical history."""
    pin = operation.pin()
    assert isinstance(
        projection,
        (
            ActivityAssetCreateProjection,
            ActivityAssetInspectProjection,
            ActivityAssetCorrectProjection,
            ActivityAssetForecastProjection,
            ActivityAssetClaimProjection,
            ActivityAssetFilingHandoffProjection,
            ActivityAssetDescribeProjection,
            ActivityAssetDisposeProjection,
            ActivityAssetDisposalCalculateProjection,
            ActivityAssetListProjection,
            ActivityAssetPlanProjection,
            ActivityAssetTimelineProjection,
            ActivityAssetFormOptionsProjection,
            ActivityAssetAcquisitionCandidatesProjection,
        ),
    )
    assert isinstance(projection.authority, ActivityAssetAuthorityProvenance)
    assert projection.authority.logical_generation == pin.logical_generation
    assert projection.authority.reader_incarnation == pin.reader_incarnation
    assert projection.outcome == "succeeded"

    if definition_id == ACTIVITY_ASSET_CREATE_OPERATION_DEFINITION_ID:
        assert isinstance(payload, ActivityAssetCreateRequest)
        assert isinstance(projection, ActivityAssetCreateProjection)
        revision = payload.revision.to_domain()
        assert before == ActivityAssetHistory()
        assert after.revisions == (revision,)
        assert after.claims == ()
        descriptor = after.current_descriptor(revision.asset_id)
        assert descriptor is not None
        assert descriptor.facts == payload.descriptor
        assert projection.history is not None
        assert projection.history.to_domain() == after
        return

    if definition_id == ACTIVITY_ASSET_INSPECT_OPERATION_DEFINITION_ID:
        assert isinstance(payload, ActivityAssetInspectRequest)
        assert isinstance(projection, ActivityAssetInspectProjection)
        expected_revisions = tuple(item for item in before.revisions if item.asset_id == payload.asset_id)
        assert after == before
        assert projection.asset_id == payload.asset_id
        assert projection.revisions is not None
        assert tuple(item.revision.to_domain() for item in projection.revisions) == expected_revisions
        assert tuple(item.revision_id for item in projection.revisions) == tuple(
            item.revision_id for item in expected_revisions
        )
        return

    if definition_id == ACTIVITY_ASSET_CORRECT_OPERATION_DEFINITION_ID:
        assert isinstance(payload, ActivityAssetCorrectRequest)
        assert isinstance(projection, ActivityAssetCorrectProjection)
        assert after.revisions == (*before.revisions, payload.revision.to_domain())
        assert after.claims == before.claims
        assert projection.history is not None
        assert projection.history.to_domain() == after
        return

    if definition_id == ACTIVITY_ASSET_FORECAST_OPERATION_DEFINITION_ID:
        assert isinstance(payload, ActivityAssetForecastRequest)
        assert isinstance(projection, ActivityAssetForecastProjection)
        revision = max(
            (item for item in before.revisions if item.asset_id == payload.asset_id),
            key=lambda item: item.revision_number,
        )
        expected = forecast_activity_asset_charge(
            revision,
            modelo_100_revision=operation.revision_for_context(
                "100",
                filing_year=payload.covered_from.year,
                period="0A",
            ),
            authority_generation=pin.logical_generation,
            covered_from=payload.covered_from,
            covered_until=payload.covered_until,
            history=asset_schedule_history(
                before.claims,
                before.revisions,
                asset_id=payload.asset_id,
                tax_year=payload.covered_from.year,
                excluding_claim_id=payload.supersedes_claim_id,
            ),
            taxpayer_workforce=lambda: (),
            legal_reference=operation.legal_reference,
            requested_free_amount=(
                Decimal(payload.requested_free_amount.decimal) if payload.requested_free_amount is not None else None
            ),
        )
        assert after == before
        assert projection.forecast is not None
        assert projection.forecast.to_domain() == expected
        assert projection.forecast.authority_generation == pin.logical_generation
        return

    if definition_id == ACTIVITY_ASSET_CLAIM_OPERATION_DEFINITION_ID:
        assert isinstance(payload, ActivityAssetClaimRequest)
        assert isinstance(projection, ActivityAssetClaimProjection)
        revision = max(
            (item for item in before.revisions if item.asset_id == payload.forecast.asset_id),
            key=lambda item: item.revision_number,
        )
        expected_claim = AmortizationClaim.from_schedule(
            payload.forecast.to_domain(),
            asset_kind=revision.asset_kind,
            creating_operation=ACTIVITY_ASSET_CLAIM_OPERATION_DEFINITION_ID,
            supersedes_claim_id=payload.supersedes_claim_id,
        )
        assert len(after.claims) == len(before.claims) + 1
        assert after.claims[:-1] == before.claims
        assert after.claims[-1] == expected_claim
        assert projection.claim_id == expected_claim.claim_id
        assert projection.claim_result is not None
        result = projection.claim_result.to_domain()
        assert result.claim == expected_claim
        assert result.history == after
        assert result.reused_existing_claim is False
        return

    if definition_id == ACTIVITY_ASSET_FILING_HANDOFF_OPERATION_DEFINITION_ID:
        assert isinstance(payload, ActivityAssetFilingHandoffRequest)
        assert isinstance(projection, ActivityAssetFilingHandoffProjection)
        assert after == before
        assert (projection.tax_year, projection.m130_period) == (payload.tax_year, payload.m130_period)
        assert projection.filing_handoff is not None
        handoff = projection.filing_handoff.to_domain()
        assert handoff.material_m100 == project_m100(
            after.claims,
            asset_kind=AssetKind.MATERIAL,
            tax_year=payload.tax_year,
        )
        # EUR 300.00 at the published 25% for the full year 2025.
        assert handoff.material_m130.amount == Decimal("75.00")
        assert [item.amount for item in handoff.material_m130.contributions] == [Decimal("75.00")]
        assert handoff.intangible_m130.contributions == ()
        return

    if isinstance(projection, ActivityAssetDisposeProjection):
        assert isinstance(payload, ActivityAssetDisposeRequest)
        assert projection.history is not None
        assert projection.history.to_domain() == after
        recorded = after.revisions[-1].disposal
        assert recorded is not None
        assert recorded.disposal_date == payload.disposal.disposal_date
        assert after.revisions[-1].out_of_service_date == date(2025, 7, 1)
        return

    if isinstance(projection, ActivityAssetDisposalCalculateProjection):
        assert after == before
        assert projection.calculation is not None
        # 250.00 received, 10.00 of costs: the seeded element's cost of 300.00 has no claim
        # behind it, so the reduction is the 2025 minimum and it is the same under any table.
        assert projection.calculation.transmission_value is not None
        assert projection.calculation.transmission_value.decimal == "250.00"
        assert projection.calculation.transmission_costs is not None
        assert projection.calculation.transmission_costs.decimal == "10.00"
        return

    assert after == before or definition_id == ACTIVITY_ASSET_DESCRIBE_OPERATION_DEFINITION_ID

    if definition_id == ACTIVITY_ASSET_DESCRIBE_OPERATION_DEFINITION_ID:
        assert isinstance(payload, ActivityAssetDescribeRequest)
        assert isinstance(projection, ActivityAssetDescribeProjection)
        assert after.same_tax_facts(before)
        descriptor = after.current_descriptor(payload.asset_id)
        assert descriptor is not None
        assert descriptor.facts == payload.descriptor
        assert projection.history is not None
        assert projection.history.to_domain() == after
        return

    if definition_id == ACTIVITY_ASSET_LIST_OPERATION_DEFINITION_ID:
        assert isinstance(projection, ActivityAssetListProjection)
        assert projection.rows is not None
        assert [row.basis.decimal for row in projection.rows] == ["300.00"]
        return

    if definition_id == ACTIVITY_ASSET_PLAN_OPERATION_DEFINITION_ID:
        assert isinstance(projection, ActivityAssetPlanProjection)
        assert projection.rows is not None
        assert projection.rows[0].tax_year == 2025
        assert projection.rows[0].planned is not None
        assert projection.rows[0].planned.decimal == "75.00"
        assert projection.limits is not None
        assert projection.limits.class_key == "equipo-proceso-informacion"
        return

    if definition_id == ACTIVITY_ASSET_TIMELINE_OPERATION_DEFINITION_ID:
        assert isinstance(projection, ActivityAssetTimelineProjection)
        assert projection.events is not None
        assert [event.kind.value for event in projection.events] == ["revision", "claim"]
        assert projection.events[1].claim is not None
        assert projection.events[1].claim.matches_current_schedule is True
        return

    if definition_id == ACTIVITY_ASSET_FORM_OPTIONS_OPERATION_DEFINITION_ID:
        assert isinstance(projection, ActivityAssetFormOptionsProjection)
        assert projection.options is not None
        assert "equipo-proceso-informacion" in {group.class_key for group in projection.options.table_groups}
        return

    if definition_id == ACTIVITY_ASSET_ACQUISITION_CANDIDATES_OPERATION_DEFINITION_ID:
        assert isinstance(projection, ActivityAssetAcquisitionCandidatesProjection)
        assert projection.candidates == ()
        return

    raise AssertionError(f"unknown activity-asset conformance operation: {definition_id}")


__all__ = [
    "ActivityAssetSeed",
    "activity_asset_revision",
    "assert_activity_asset_conformance_result",
    "seed_acquisition_transaction",
    "seed_activity_asset",
]
