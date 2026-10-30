"""Synthetic activity-asset revisions and an action stub for the activity-asset screen tests.

The activity-asset screen is exercised from this package and, through the
root's in-flight guard, from ``entrypoints.tui.tests``; both build the same
revision and action stub from here.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from threading import Event
from uuid import UUID

from .....application.actividad_asset.activity_asset_contracts import ActivityAssetAuthorityProvenance
from .....application.actividad_asset.activity_asset_projections import ActivityAssetPlanProjection
from .....application.actividad_asset.activity_asset_read_models import (
    ActivityAssetAcquisitionCandidate,
    ActivityAssetClaimState,
    ActivityAssetDisposalCalculationView,
    ActivityAssetElectionLimits,
    ActivityAssetFormOptionsView,
    ActivityAssetListRow,
    ActivityAssetPlanRow,
    ActivityAssetTimelineEvent,
)
from .....application.actividad_asset.history import ActivityAssetHistory, ActivityAssetHistoryClaimResult
from .....application.actividad_asset.operation_dtos import ActivityAssetDisposalSnapshot
from .....application.actividad_asset.operations import ActivityAssetFilingHandoff, M130AccrualProjection
from .....application.actividad_asset.schedule_walk import PlanFigureAbsence
from .....application.operations.public_scalar import PublicDecimal
from .....domain.renta.actividad_asset.claims import ClaimProjection
from .....domain.renta.actividad_asset.disposal import ActivityAssetDisposalReason
from .....domain.renta.actividad_asset.election import (
    AcquiredCondition,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    DirectEstimationRegime,
)
from .....domain.renta.actividad_asset.lifecycle import (
    AcquisitionLineageReference,
    AcquisitionShape,
    ActivityAssetBasis,
    ActivityAssetRevision,
    AssetBasisStage,
    AssetKind,
    OpeningAmortizationHistory,
    OpeningHistoryStatus,
)
from .....domain.renta.actividad_asset.register_records import ActivityAssetDescriptorFacts
from .....domain.renta.actividad_asset.schedule import (
    AssetScheduleHistory,
    ScheduleAuthority,
    ScheduledAmortizationCharge,
    schedule_charge,
)
from ..models_actividad_asset import (
    ActivityAssetClaimRequestV1,
    ActivityAssetCorrectionRequestV1,
    ActivityAssetCreationRequestV1,
    ActivityAssetFilingRequestV1,
    ActivityAssetForecastRequestV1,
    ActivityAssetInspectionV1,
)


def activity_asset_revision(asset_id: str) -> ActivityAssetRevision:
    """A first revision of a new, linearly amortised material asset."""
    return ActivityAssetRevision(
        asset_id=asset_id,
        revision_number=1,
        acquisition=AcquisitionLineageReference(
            observed_transaction_id="1" * 64,
            invoice_evidence_id=f"invoice-{asset_id}",
            evidence_fingerprint="2" * 64,
        ),
        acquisition_shape=AcquisitionShape.PRIMARY_PURCHASE,
        asset_kind=AssetKind.MATERIAL,
        basis=ActivityAssetBasis(
            stage=AssetBasisStage.BUSINESS_ALLOCATED,
            basis_amount=Decimal("2000"),
            non_deductible_iva=Decimal("0"),
            prior_allocation_provenance="ledger allocation source",
        ),
        in_service_date=date(2025, 1, 1),
        opening_history=OpeningAmortizationHistory(status=OpeningHistoryStatus.KNOWN, accumulated_amount=Decimal("0")),
        acquired_condition=AcquiredCondition.NEW,
        amortization=ActivityAssetAmortizationElection(
            regime=DirectEstimationRegime.SIMPLIFIED,
            method=AmortizationMethod.LINEAR,
            authority_class_key="equipo-informacion-software",
        ),
    )


def activity_asset_forecast(
    revision: ActivityAssetRevision,
    *,
    covered_from: date,
    covered_until: date,
    history: AssetScheduleHistory,
    requested_free_amount: Decimal | None = None,
) -> ScheduledAmortizationCharge:
    """Schedule one charge for *revision* under a fixture-only authority."""
    return schedule_charge(
        revision,
        ScheduleAuthority(
            tax_year=covered_from.year,
            asset_kind=revision.asset_kind,
            method=revision.amortization.method,
            election_fingerprint=revision.amortization.fingerprint,
            annual_rate=Decimal("0.26"),
            maximum_period_ends_on=date(2035, 1, 1),
            authority_generation="tui-screen-fixture-v1",
            source_reference="TUI screen fixture only",
        ),
        covered_from=covered_from,
        covered_until=covered_until,
        history=history,
        requested_free_amount=requested_free_amount,
    )


class ActivityAssetActionStub:
    """Supply typed screen responses without reopening profile services."""

    def __init__(
        self,
        revision: ActivityAssetRevision,
        *,
        forecast_error: Exception | None = None,
        create_started: Event | None = None,
        create_release: Event | None = None,
        create_error: Exception | None = None,
        inspect_error: Exception | None = None,
    ) -> None:
        self.revision = revision
        self.forecast_error = forecast_error
        self.inspect_error = inspect_error
        self.create_started = create_started
        self.create_release = create_release
        self.create_error = create_error
        self.requests: list[tuple[str, object]] = []

    def create(self, request: ActivityAssetCreationRequestV1) -> ActivityAssetInspectionV1:
        self.requests.append(("create", request))
        if self.create_started is not None:
            self.create_started.set()
        if self.create_release is not None and not self.create_release.wait(timeout=2.0):
            raise RuntimeError("test action was not released")
        if self.create_error is not None:
            raise self.create_error
        return ActivityAssetInspectionV1(asset_id=request.revision.asset_id, revisions=(request.revision,))

    def inspect(self, asset_id: str) -> ActivityAssetInspectionV1:
        self.requests.append(("inspect", asset_id))
        if self.inspect_error is not None:
            raise self.inspect_error
        return ActivityAssetInspectionV1(asset_id=asset_id, revisions=(self.revision,))

    def correct(self, request: ActivityAssetCorrectionRequestV1) -> ActivityAssetInspectionV1:
        self.requests.append(("correct", request))
        return ActivityAssetInspectionV1(asset_id=request.revision.asset_id, revisions=(request.revision,))

    def forecast(self, request: ActivityAssetForecastRequestV1) -> ScheduledAmortizationCharge:
        self.requests.append(("forecast", request))
        if self.forecast_error is not None:
            raise self.forecast_error
        history = AssetScheduleHistory()
        return activity_asset_forecast(
            self.revision,
            covered_from=request.covered_from,
            covered_until=request.covered_until,
            history=history,
            requested_free_amount=request.requested_free_amount,
        )

    def record_claim(self, request: ActivityAssetClaimRequestV1) -> ActivityAssetHistoryClaimResult:
        self.requests.append(("record_claim", request))
        raise AssertionError("this screen test does not exercise claim execution")

    def describe(self, asset_id: str, descriptor: ActivityAssetDescriptorFacts) -> ActivityAssetHistory:
        self.requests.append(("describe", (asset_id, descriptor)))
        return ActivityAssetHistory(revisions=(self.revision,)).describe(asset_id, descriptor)

    def plan(self, asset_id: str) -> ActivityAssetPlanProjection:
        self.requests.append(("plan", asset_id))
        return ActivityAssetPlanProjection(
            profile_id=UUID(int=1),
            authority=ActivityAssetAuthorityProvenance(
                logical_generation="a" * 64,
                reader_incarnation="b" * 64,
            ),
            outcome="succeeded",
            asset_id=asset_id,
            rows=(
                ActivityAssetPlanRow(
                    tax_year=2025,
                    method=AmortizationMethod.LINEAR,
                    planned=PublicDecimal(decimal="520.00"),
                    claimed=PublicDecimal(decimal="0.00"),
                    claim_state=ActivityAssetClaimState.NOT_DUE,
                    minimum_through=PublicDecimal(decimal="130.00"),
                ),
                ActivityAssetPlanRow(
                    tax_year=2036,
                    method=AmortizationMethod.LINEAR,
                    absence=PlanFigureAbsence.PERIOD_ELAPSED,
                    claimed=PublicDecimal(decimal="0.00"),
                    claim_state=ActivityAssetClaimState.NOT_DUE,
                    minimum_through=PublicDecimal(decimal="130.00"),
                    minimum_complete=False,
                ),
            ),
            limits=ActivityAssetElectionLimits(
                class_key="equipo-informacion-software",
                maximum_period_ends_on=date(2035, 1, 1),
            ),
        )

    def dispose(self, asset_id: str, disposal: ActivityAssetDisposalSnapshot) -> ActivityAssetHistory:
        self.requests.append(("dispose", (asset_id, disposal)))
        return ActivityAssetHistory(revisions=(self.revision,))

    def disposal_calculate(
        self, asset_id: str, disposal: ActivityAssetDisposalSnapshot | None
    ) -> ActivityAssetDisposalCalculationView:
        self.requests.append(("disposal_calculate", (asset_id, disposal)))
        return ActivityAssetDisposalCalculationView(
            disposal_date=date(2026, 6, 30),
            reason=ActivityAssetDisposalReason.SALE,
            acquisition_value=PublicDecimal(decimal="2000.00"),
            deducted=PublicDecimal(decimal="777.86"),
            minimum=PublicDecimal(decimal="299.18"),
            reduction=PublicDecimal(decimal="777.86"),
            excess=PublicDecimal(decimal="0.00"),
            net_value=PublicDecimal(decimal="1222.14"),
            transmission_value=PublicDecimal(decimal="2000.00"),
            transmission_costs=PublicDecimal(decimal="100.00"),
            result=PublicDecimal(decimal="677.86"),
            route_changed_by_later_affectation=False,
            years=(),
            findings=(),
        )

    def acquisition_candidates(self) -> tuple[ActivityAssetAcquisitionCandidate, ...]:
        self.requests.append(("acquisition_candidates", None))
        return ()

    def list_elements(self) -> tuple[ActivityAssetListRow, ...]:
        raise AssertionError("this screen test does not exercise list execution")

    def timeline(self, asset_id: str) -> tuple[ActivityAssetTimelineEvent, ...]:
        del asset_id
        raise AssertionError("this screen test does not exercise timeline execution")

    def form_options(self, asset_kind: AssetKind, tax_year: int) -> ActivityAssetFormOptionsView:
        del asset_kind, tax_year
        raise AssertionError("this screen test does not exercise form options")

    def filing_handoff(self, request: ActivityAssetFilingRequestV1) -> ActivityAssetFilingHandoff:
        self.requests.append(("filing_handoff", request))
        return ActivityAssetFilingHandoff(
            material_m100=ClaimProjection(
                target_casilla_id="0113", tax_year=request.tax_year, claim_ids=(), amount=Decimal("0.00")
            ),
            intangible_m100=ClaimProjection(
                target_casilla_id="0114", tax_year=request.tax_year, claim_ids=(), amount=Decimal("0.00")
            ),
            material_m130=M130AccrualProjection(
                target_casilla_id="02", tax_year=request.tax_year, amount=Decimal("0.00")
            ),
            intangible_m130=M130AccrualProjection(
                target_casilla_id="02", tax_year=request.tax_year, amount=Decimal("0.00")
            ),
        )
