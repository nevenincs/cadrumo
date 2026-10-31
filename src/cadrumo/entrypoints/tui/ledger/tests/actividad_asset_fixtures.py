"""Synthetic activity-asset revisions and an action stub for the activity-asset screen tests.

The activity-asset screen is exercised from this package and, through the
root's in-flight guard, from ``entrypoints.tui.tests``; both build the same
revision and action stub from here.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from threading import Event
from uuid import UUID

from .....application.actividad_asset.activity_asset_contracts import ActivityAssetAuthorityProvenance
from .....application.actividad_asset.activity_asset_projections import (
    ActivityAssetListProjection,
    ActivityAssetPlanProjection,
)
from .....application.actividad_asset.activity_asset_read_models import (
    OPENING_HISTORY_MISSING_KEY,
    ActivityAssetAcquisitionCandidate,
    ActivityAssetClaimableInterval,
    ActivityAssetClaimState,
    ActivityAssetDisposalCalculationView,
    ActivityAssetEdition,
    ActivityAssetElectionLimits,
    ActivityAssetFindingCounts,
    ActivityAssetFormOptionsView,
    ActivityAssetListDisposal,
    ActivityAssetListRow,
    ActivityAssetPlanRow,
    ActivityAssetRegisterState,
    ActivityAssetTimelineChange,
    ActivityAssetTimelineEvent,
    ActivityAssetTimelineEventKind,
    activity_asset_label_key,
    remedy_field_key,
    timeline_field_key,
    timeline_token_key,
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
from .....domain.renta.actividad_asset.register_records import ActivityAssetDescriptorFacts, ActivityAssetEventKind
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
        list_rows: tuple[ActivityAssetListRow, ...] = (),
        register_default_year: int | None = None,
        timeline_events: tuple[ActivityAssetTimelineEvent, ...] = (),
        form_options_view: ActivityAssetFormOptionsView | None = None,
    ) -> None:
        self.revision = revision
        self.list_rows = list_rows
        self.register_default_year = register_default_year
        self.timeline_events = timeline_events
        self.form_options_view = form_options_view
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
                    claim_state=ActivityAssetClaimState.MISSING,
                    minimum_through=PublicDecimal(decimal="130.00"),
                    claimable_intervals=(
                        ActivityAssetClaimableInterval(
                            covered_from=date(2025, 1, 1),
                            covered_until=date(2026, 1, 1),
                            covered_through=date(2025, 12, 31),
                        ),
                    ),
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
                ActivityAssetPlanRow(
                    tax_year=2037,
                    method=AmortizationMethod.LINEAR,
                    absence=PlanFigureAbsence.INCOMPLETE,
                    absence_reason_key=OPENING_HISTORY_MISSING_KEY,
                    absence_remedy_field_key=remedy_field_key(OPENING_HISTORY_MISSING_KEY),
                    claimed=PublicDecimal(decimal="0.00"),
                    claim_state=ActivityAssetClaimState.MISSING,
                ),
                ActivityAssetPlanRow(
                    tax_year=2038,
                    method=AmortizationMethod.LINEAR,
                    absence=PlanFigureAbsence.BASIS_EXHAUSTED,
                    applies=False,
                    claimed=PublicDecimal(decimal="0.00"),
                    claim_state=ActivityAssetClaimState.NOT_DUE,
                ),
            ),
            limits=ActivityAssetElectionLimits(
                class_key="equipo-informacion-software",
                class_label="Information equipment and software",
                maximum_period_ends_on=date(2035, 1, 1),
                maximum_period_last_day=date(2034, 12, 31),
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

    def list_elements(self) -> ActivityAssetListProjection:
        self.requests.append(("list", None))
        return ActivityAssetListProjection(
            profile_id=UUID(int=1),
            authority=ActivityAssetAuthorityProvenance(logical_generation="a" * 64, reader_incarnation="b" * 64),
            outcome="succeeded",
            rows=self.list_rows,
            default_year=self.register_default_year,
        )

    def timeline(self, asset_id: str) -> tuple[ActivityAssetTimelineEvent, ...]:
        self.requests.append(("timeline", asset_id))
        return self.timeline_events

    def form_options(self, asset_kind: AssetKind, tax_year: int) -> ActivityAssetFormOptionsView:
        self.requests.append(("form_options", (asset_kind, tax_year)))
        if self.form_options_view is None:
            raise AssertionError("this screen test does not exercise form options")
        return self.form_options_view

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


def _register_row(
    asset_id: str,
    name: str,
    state: ActivityAssetRegisterState,
    **served: object,
) -> ActivityAssetListRow:
    """One element of the register, with the facts every element carries and the ones a case states."""
    return ActivityAssetListRow.model_validate(
        {
            "asset_id": asset_id,
            "name": name,
            "state": state,
            "asset_kind": AssetKind.MATERIAL,
            "in_service_date": date(2025, 1, 1),
            "method": AmortizationMethod.LINEAR,
            "revision_number": 1,
            "basis": PublicDecimal(decimal="2000.00"),
            "findings": ActivityAssetFindingCounts(missing=0, incomplete=0, conflict=0, stale=0),
            **served,
        },
    )


def activity_asset_list_rows() -> tuple[ActivityAssetListRow, ...]:
    """Three elements: one with a figure and a year to claim, one whose opening is unknown, one with a baja."""
    return (
        _register_row(
            "laptop",
            "Office laptop",
            ActivityAssetRegisterState.IN_SERVICE,
            pending=PublicDecimal(decimal="1480.00"),
            findings=ActivityAssetFindingCounts(missing=2, incomplete=0, conflict=0, stale=0),
            default_claim_year=2025,
        ),
        _register_row(
            "desk",
            "Standing desk",
            ActivityAssetRegisterState.IN_SERVICE,
            opening_remedy_field_key=remedy_field_key(OPENING_HISTORY_MISSING_KEY),
        ),
        _register_row(
            "printer",
            "Sold printer",
            ActivityAssetRegisterState.OUT_OF_SERVICE,
            pending=PublicDecimal(decimal="900.00"),
            pending_applies=False,
            disposal=ActivityAssetListDisposal(
                disposal_date=date(2026, 6, 30),
                reason=ActivityAssetDisposalReason.SALE,
                reason_key=activity_asset_label_key("disposal_reason", ActivityAssetDisposalReason.SALE),
            ),
        ),
    )


def activity_asset_timeline_events() -> tuple[ActivityAssetTimelineEvent, ...]:
    """A creation and a correction of the method, each with the facts it changed."""
    return (
        ActivityAssetTimelineEvent(
            sequence=1,
            recorded_at=datetime(2025, 2, 3, 10, 0, tzinfo=UTC),
            kind=ActivityAssetEventKind.REVISION,
            event_kind=ActivityAssetTimelineEventKind.CREATED,
            asset_id="laptop",
            record_id="record-one",
            effect_date=date(2025, 1, 1),
            affects_calculation=True,
        ),
        ActivityAssetTimelineEvent(
            sequence=2,
            kind=ActivityAssetEventKind.REVISION,
            event_kind=ActivityAssetTimelineEventKind.CORRECTED,
            asset_id="laptop",
            record_id="record-two",
            effect_date=date(2025, 1, 1),
            changes=(
                ActivityAssetTimelineChange(
                    field="in_service_date",
                    field_key=timeline_field_key("in_service_date"),
                    before="2025-01-01",
                    after="2025-03-15",
                ),
                ActivityAssetTimelineChange(
                    field="amortization.method",
                    field_key=timeline_field_key("amortization.method"),
                    before="linear",
                    after="constant_percentage",
                    before_key=timeline_token_key("amortization.method", "linear"),
                    after_key=timeline_token_key("amortization.method", "constant_percentage"),
                ),
            ),
            affects_calculation=False,
        ),
    )


def activity_asset_form_options(*, m130_periods: tuple[str, ...]) -> ActivityAssetFormOptionsView:
    """Form options whose only served content of interest is the Modelo 130 periods."""
    return ActivityAssetFormOptionsView(
        tax_year=2031,
        asset_kind=AssetKind.MATERIAL,
        regime=DirectEstimationRegime.SIMPLIFIED,
        edition=ActivityAssetEdition(revision_id="fixture-edition", authored_filing_year=2031, projected=False),
        acquisition_shapes=(),
        declared_activities=(),
        methods=(AmortizationMethod.LINEAR,),
        method_facts=(),
        table_groups=(),
        disposal_reasons=(),
        m130_periods=m130_periods,
    )
