"""Shared application operations for IRPF activity-asset frontends."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.money.rounding import round_to_cents
from ...core.period import Period
from ...core.tipos_actividad import TipoActividad
from ...domain.calculations.registry.actividad_asset_bindings import activity_asset_form_options
from ...domain.calculations.registry.errors import RegistryError
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.renta.actividad_asset.claims import (
    AmortizationClaim,
    ClaimProjection,
    asset_schedule_history,
    effective_claims,
    project_m100,
    record_claim,
)
from ...domain.renta.actividad_asset.election import FREE_AMOUNT_METHODS, DirectEstimationRegime
from ...domain.renta.actividad_asset.errors import (
    ActividadAssetClaimConflictError,
    ActividadAssetError,
    ActividadAssetValidationError,
)
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision, AssetKind
from ...domain.renta.actividad_asset.register_records import ActivityAssetDescriptorFacts
from ...domain.renta.actividad_asset.schedule import ScheduleAuthority, ScheduledAmortizationCharge
from ..operations.public_scalar import project_scalar
from .acquisition_ledger import require_acquisition_in_ledger
from .activity_asset_read_models import (
    ActivityAssetAcquisitionCandidate,
    ActivityAssetEdition,
    ActivityAssetElectionLimits,
    ActivityAssetFormOptionsView,
    ActivityAssetListRow,
    ActivityAssetNotTableBoundReason,
    ActivityAssetPlanRow,
    ActivityAssetTableGroup,
    ActivityAssetTimelineEvent,
)
from .history import ActivityAssetHistory, ActivityAssetHistoryClaimResult
from .ports import (
    AcquisitionLedgerReader,
    ActivityAssetForecastOperation,
    ActivityAssetHistoryRepository,
    TaxpayerModalityReader,
)
from .register_reads import (
    RegisterReadContext,
    acquisition_candidates,
    election_limits,
    element_list,
    element_plan,
    element_timeline,
)
from .schedule_walk import M130ElementOutcome, m130_register_accruals
from .service import ActivityAssetHistoryService


class M130Contribution(BaseModel):
    """One amount behind Modelo 130 casilla 02, resting on one claim or on one schedule."""

    model_config = STRICT_FROZEN_CONFIG

    asset_id: str = Field(min_length=1, max_length=128)
    amount: Decimal
    claim_id: str | None = None
    schedule_fingerprint: str | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _one_source(self) -> Self:
        if (self.claim_id is None) == (self.schedule_fingerprint is None):
            raise ValueError("a Modelo 130 contribution rests on exactly one claim or one schedule")
        return self


class M130AccrualProjection(BaseModel):
    """What one asset kind accrued in the year through the period's end.

    ``unavailable_asset_ids`` names elements whose schedule could not be worked
    out, so an amount that leaves them out says so.
    """

    model_config = STRICT_FROZEN_CONFIG

    target_casilla_id: Literal["02"] = "02"
    tax_year: int
    amount: Decimal
    contributions: tuple[M130Contribution, ...] = ()
    unavailable_asset_ids: tuple[str, ...] = ()


class ActivityAssetFilingHandoff(BaseModel):
    """Non-consuming projections for both supported IRPF filing destinations."""

    model_config = STRICT_FROZEN_CONFIG

    material_m100: ClaimProjection
    intangible_m100: ClaimProjection
    material_m130: M130AccrualProjection
    intangible_m130: M130AccrualProjection


class SupersedingClaimRequest(BaseModel):
    """A recorded claim a correction replaces; its interval carries over and the backend works out the figure."""

    model_config = STRICT_FROZEN_CONFIG

    supersedes_claim_id: str = Field(min_length=64, max_length=64)
    requested_free_amount: Decimal | None = None


@dataclass(frozen=True, slots=True)
class ActivityAssetRegisterAuthority:
    """The pinned-authority and profile facts the register's reads and handoff depend on."""

    edition: Callable[[int], tuple[ActivityAssetEdition, ModeloRevision]]
    agrarian_activities: Callable[[date], frozenset[TipoActividad]]
    foral_territory: Callable[[], bool]
    claim_consumers: Callable[[Iterable[str]], Mapping[str, tuple[str, ...]]]
    today: Callable[[], date]
    schedule_authority: Callable[[ActivityAssetRevision, int], ScheduleAuthority]


class ActivityAssetOperations:
    """One use-case boundary shared by CLI, TUI, and installed acceptance flows."""

    def __init__(
        self,
        *,
        repository: ActivityAssetHistoryRepository,
        ledger: AcquisitionLedgerReader,
        forecast_operation: ActivityAssetForecastOperation,
        taxpayer_modality: TaxpayerModalityReader,
        register_authority: ActivityAssetRegisterAuthority,
    ) -> None:
        """Bind the operations to one bucket-scoped history, ledger, taxpayer profile and authority pin."""
        self._service = ActivityAssetHistoryService(repository=repository)
        self._ledger = ledger
        self._forecast_operation = forecast_operation
        self._taxpayer_modality = taxpayer_modality
        self._authority = register_authority

    def create(
        self,
        revision: ActivityAssetRevision,
        descriptor: ActivityAssetDescriptorFacts,
        *,
        recorded_at: datetime | None = None,
        origin: str | None = None,
    ) -> ActivityAssetHistory:
        """Create an asset from its first immutable revision and first descriptor, in one write."""
        if revision.revision_number != 1:
            raise ActividadAssetValidationError(
                translated_message="ledger.actividad_asset.errors.creation_requires_first_revision"
            )
        history = self._service.reopen()
        if any(item.asset_id == revision.asset_id for item in history.revisions):
            raise ActividadAssetValidationError(translated_message="ledger.actividad_asset.errors.asset_already_exists")
        require_acquisition_in_ledger(revision, self._ledger)
        return self._service.apply(
            lambda current: current.append_revision(revision, recorded_at=recorded_at, origin=origin).describe(
                revision.asset_id,
                descriptor,
                recorded_at=recorded_at,
                origin=origin,
            ),
        )

    def describe(
        self,
        asset_id: str,
        descriptor: ActivityAssetDescriptorFacts,
        *,
        recorded_at: datetime | None = None,
        origin: str | None = None,
    ) -> ActivityAssetHistory:
        """Append an element's descriptive facts; no revision, claim or calculation changes."""
        return self._service.apply(
            lambda current: current.describe(asset_id, descriptor, recorded_at=recorded_at, origin=origin),
        )

    def inspect(self, asset_id: str) -> tuple[ActivityAssetRevision, ...]:
        """Return the complete immutable revision chain for one asset."""
        revisions = tuple(item for item in self._service.reopen().revisions if item.asset_id == asset_id)
        if not revisions:
            raise ActividadAssetValidationError(translated_message="ledger.actividad_asset.errors.asset_not_found")
        return revisions

    def correct(
        self,
        revision: ActivityAssetRevision,
        superseding_claims: tuple[SupersedingClaimRequest, ...] = (),
        *,
        recorded_at: datetime | None = None,
        origin: str | None = None,
    ) -> ActivityAssetHistory:
        """Append a correction and the claims replacing what it invalidates, in one compare-and-swap.

        A correction can lower the basis below a recorded claim only together with
        that claim's replacement, so the two are validated on their final state.
        """
        history = self._service.reopen()
        if any(item.revision_id == revision.revision_id for item in history.revisions):
            return history
        current = self.inspect(revision.asset_id)[-1]
        if (
            revision.revision_number != current.revision_number + 1
            or revision.supersedes_revision_id != current.revision_id
        ):
            raise ActividadAssetValidationError(
                translated_message="ledger.actividad_asset.errors.correction_must_supersede_current"
            )
        require_acquisition_in_ledger(revision, self._ledger)
        claims = self._superseding_claims(revision, superseding_claims, history, origin=origin)

        def mutation(latest: ActivityAssetHistory) -> ActivityAssetHistory:
            if not latest.same_tax_facts(history):
                raise ActividadAssetClaimConflictError(
                    translated_message="ledger.actividad_asset.errors.history_changed_after_forecast",
                )
            return latest.apply_correction(revision, claims, recorded_at=recorded_at, origin=origin)

        return self._service.apply(mutation)

    def _superseding_claims(
        self,
        revision: ActivityAssetRevision,
        requests: tuple[SupersedingClaimRequest, ...],
        history: ActivityAssetHistory,
        *,
        origin: str | None,
    ) -> tuple[AmortizationClaim, ...]:
        """Forecast each replacement under the new revision, earliest first, on the state the earlier ones leave."""
        if not requests:
            return ()
        effective = {claim.claim_id: claim for claim in effective_claims(history.claims)}
        targets: list[tuple[AmortizationClaim, SupersedingClaimRequest]] = []
        for request in requests:
            superseded = effective.get(request.supersedes_claim_id)
            if superseded is None or superseded.asset_id != revision.asset_id:
                raise ActividadAssetValidationError(
                    translated_message="ledger.actividad_asset.errors.superseded_claim_not_effective",
                )
            targets.append((superseded, request))
        _require_profile_modality(revision.amortization.regime, self._taxpayer_modality())
        revisions = (*history.revisions, revision)
        working = history.claims
        recorded: list[AmortizationClaim] = []
        for superseded, request in sorted(targets, key=lambda item: item[0].covered_from):
            charge = self._forecast_operation(
                revision,
                covered_from=superseded.covered_from,
                covered_until=superseded.covered_until,
                history=asset_schedule_history(
                    tuple(claim for claim in working if claim.tax_year <= superseded.tax_year),
                    revisions,
                    asset_id=revision.asset_id,
                    tax_year=superseded.tax_year,
                    excluding_claim_id=superseded.claim_id,
                ),
                requested_free_amount=request.requested_free_amount,
            )
            claim = AmortizationClaim.from_schedule(
                charge,
                asset_kind=revision.asset_kind,
                creating_operation=origin or revision.asset_id,
                supersedes_claim_id=superseded.claim_id,
            )
            working = record_claim(working, claim).claims
            recorded.append(claim)
        return tuple(recorded)

    def forecast(
        self,
        *,
        asset_id: str,
        covered_from: date,
        covered_until: date,
        requested_free_amount: Decimal | None = None,
        supersedes_claim_id: str | None = None,
    ) -> ScheduledAmortizationCharge:
        """Calculate a forecast under the current revision's election without recording it.

        A forecast for a superseding claim leaves out the effective claim it
        will replace, exactly as recording that claim does.
        """
        if supersedes_claim_id is not None and not any(
            claim.claim_id == supersedes_claim_id and claim.asset_id == asset_id
            for claim in effective_claims(self._service.reopen().claims)
        ):
            raise ActividadAssetValidationError(
                translated_message="ledger.actividad_asset.errors.superseded_claim_not_effective"
            )
        return self._forecast(
            asset_id=asset_id,
            covered_from=covered_from,
            covered_until=covered_until,
            requested_free_amount=requested_free_amount,
            excluding_claim_id=supersedes_claim_id,
        )

    def _forecast(
        self,
        *,
        asset_id: str,
        covered_from: date,
        covered_until: date,
        requested_free_amount: Decimal | None,
        excluding_claim_id: str | None,
    ) -> ScheduledAmortizationCharge:
        history = self._service.reopen()
        revision = self.inspect(asset_id)[-1]
        _require_profile_modality(revision.amortization.regime, self._taxpayer_modality())
        return self._forecast_operation(
            revision,
            covered_from=covered_from,
            covered_until=covered_until,
            history=asset_schedule_history(
                history.claims,
                history.revisions,
                asset_id=asset_id,
                tax_year=covered_from.year,
                excluding_claim_id=excluding_claim_id,
            ),
            requested_free_amount=requested_free_amount,
        )

    def record_claim(
        self,
        forecast: ScheduledAmortizationCharge,
        *,
        creating_operation: str,
        supersedes_claim_id: str | None = None,
        recorded_at: datetime | None = None,
    ) -> ActivityAssetHistoryClaimResult:
        """Explicitly materialize a forecast as one idempotent claim operation.

        A forecast is caller-held data (the CLI receives it as JSON), so a new
        claim is recorded only when recomputing the forecast against current
        history, authority and profile reproduces it exactly.  An exact replay
        of an already recorded claim returns that claim unchanged.
        """
        current_history = self._service.reopen()
        revision = max(
            (item for item in current_history.revisions if item.asset_id == forecast.asset_id),
            key=lambda item: item.revision_number,
            default=None,
        )
        if revision is None:
            raise ActividadAssetValidationError(translated_message="ledger.actividad_asset.errors.asset_not_found")
        if revision.revision_id != forecast.asset_revision_id:
            raise ActividadAssetValidationError(
                translated_message="ledger.actividad_asset.errors.forecast_not_current_revision"
            )
        claim = AmortizationClaim.from_schedule(
            forecast,
            asset_kind=revision.asset_kind,
            creating_operation=creating_operation,
            supersedes_claim_id=supersedes_claim_id,
        )
        if any(existing.claim_id == claim.claim_id for existing in current_history.claims):
            return self._service.record_claim(claim)
        _require_profile_modality(revision.amortization.regime, self._taxpayer_modality())
        recomputed = self._forecast_operation(
            revision,
            covered_from=forecast.covered_from,
            covered_until=forecast.covered_until,
            history=asset_schedule_history(
                current_history.claims,
                current_history.revisions,
                asset_id=forecast.asset_id,
                tax_year=forecast.covered_from.year,
                excluding_claim_id=supersedes_claim_id,
            ),
            requested_free_amount=(forecast.amount if forecast.method in FREE_AMOUNT_METHODS else None),
        )
        if recomputed != forecast:
            raise ActividadAssetValidationError(
                translated_message="ledger.actividad_asset.errors.forecast_no_longer_matches"
            )
        return self._service.record_claim(claim, expected_history=current_history, recorded_at=recorded_at)

    def filing_handoff(self, *, tax_year: int, m130_period: Period) -> ActivityAssetFilingHandoff:
        """Project M100 from effective claims and M130 from the accrual route, recording nothing."""
        history = self._service.reopen()
        if history.revisions and self._authority.foral_territory():
            raise ActividadAssetValidationError(translated_message="ledger.actividad_asset.errors.foral_territory")
        period_end = m130_period.end_date
        current = {revision.asset_id: revision for revision in history.revisions}
        rows = self._ledger.load_by_ids(
            {revision.acquisition.observed_transaction_id for revision in current.values()},
        ).transactions
        accruals = m130_register_accruals(
            history,
            forecast=self._forecast_operation,
            period_end=period_end,
            activities={
                asset_id: (
                    row.tipo_actividad if (row := rows.get(revision.acquisition.observed_transaction_id)) else None
                )
                for asset_id, revision in current.items()
            },
            agrarian=self._authority.agrarian_activities(period_end) if current else frozenset(),
        )

        def m130(asset_kind: AssetKind) -> M130AccrualProjection:
            selected = tuple(accrual for accrual in accruals if accrual.revision.asset_kind is asset_kind)
            contributions = tuple(
                M130Contribution(
                    asset_id=item.asset_id,
                    amount=item.amount,
                    claim_id=item.claim_id,
                    schedule_fingerprint=item.schedule_fingerprint,
                )
                for accrual in selected
                for item in accrual.contributions
            )
            return M130AccrualProjection(
                tax_year=tax_year,
                amount=round_to_cents(sum((item.amount for item in contributions), Decimal("0"))),
                contributions=contributions,
                unavailable_asset_ids=tuple(
                    accrual.revision.asset_id
                    for accrual in selected
                    if accrual.outcome is M130ElementOutcome.UNAVAILABLE
                ),
            )

        return ActivityAssetFilingHandoff(
            material_m100=project_m100(history.claims, asset_kind=AssetKind.MATERIAL, tax_year=tax_year),
            intangible_m100=project_m100(history.claims, asset_kind=AssetKind.INTANGIBLE, tax_year=tax_year),
            material_m130=m130(AssetKind.MATERIAL),
            intangible_m130=m130(AssetKind.INTANGIBLE),
        )

    def _read_context(self, history: ActivityAssetHistory) -> RegisterReadContext:
        return RegisterReadContext(
            history=history,
            forecast=self._forecast_operation,
            edition=lambda tax_year: self._authority.edition(tax_year)[0],
            today=self._authority.today(),
        )

    def list_elements(self) -> tuple[ActivityAssetListRow, ...]:
        """Summarise every element of the register."""
        return element_list(self._read_context(self._service.reopen()))

    def plan(self, asset_id: str) -> tuple[ActivityAssetPlanRow, ...]:
        """Work out one element's plan, year by year."""
        revision = self.inspect(asset_id)[-1]
        return element_plan(revision, self._read_context(self._service.reopen()))

    def plan_limits(self, asset_id: str) -> ActivityAssetElectionLimits:
        """Read what the registry allows the element's current election, under this year's edition."""
        revision = self.inspect(asset_id)[-1]
        tax_year = max(self._authority.today().year, revision.in_service_date.year)
        try:
            _, modelo = self._authority.edition(tax_year)
            return election_limits(
                revision,
                self._authority.schedule_authority(revision, tax_year),
                activity_asset_form_options(
                    modelo,
                    tax_year=tax_year,
                    asset_kind=revision.asset_kind,
                    regime=revision.amortization.regime,
                ),
            )
        except RegistryError:
            reason_key = "ledger.actividad_asset.errors.tax_year_without_edition"
        except ActividadAssetError as error:
            reason_key = error.translated_message
        return ActivityAssetElectionLimits(
            class_key=revision.amortization.authority_class_key,
            not_table_bound=ActivityAssetNotTableBoundReason.AUTHORITY_UNAVAILABLE,
            unavailable_reason_key=reason_key,
        )

    def timeline(self, asset_id: str) -> tuple[ActivityAssetTimelineEvent, ...]:
        """List one element's history in order, with what each record changed and what used each claim."""
        self.inspect(asset_id)
        history = self._service.reopen()
        claim_ids = tuple(claim.claim_id for claim in history.claims if claim.asset_id == asset_id)
        return element_timeline(
            asset_id,
            self._read_context(history),
            used_by=self._authority.claim_consumers(claim_ids),
        )

    def form_options(self, *, asset_kind: AssetKind, tax_year: int) -> ActivityAssetFormOptionsView:
        """Read what the registry admits for an asset kind and tax year under the profile's modality."""
        regime = self._taxpayer_modality()
        edition, revision = self._authority.edition(tax_year)
        options = activity_asset_form_options(revision, tax_year=tax_year, asset_kind=asset_kind, regime=regime)
        return ActivityAssetFormOptionsView(
            tax_year=tax_year,
            asset_kind=asset_kind,
            regime=regime,
            edition=edition,
            methods=options.methods,
            table_groups=tuple(
                ActivityAssetTableGroup(
                    class_key=group.class_key,
                    maximum_coefficient=project_scalar(group.maximum_coefficient),
                    minimum_coefficient=project_scalar(group.minimum_coefficient),
                    maximum_period_years=project_scalar(group.maximum_period_years),
                )
                for group in options.table_groups
            ),
        )

    def acquisition_candidates(self) -> tuple[ActivityAssetAcquisitionCandidate, ...]:
        """List the business payments no element names as its acquisition yet."""
        return acquisition_candidates(self._ledger.load(), self._service.reopen())


def _require_profile_modality(elected: DirectEstimationRegime, declared: DirectEstimationRegime) -> None:
    """Refuse an election whose modality the taxpayer profile does not declare (RIRPF art. 28.3)."""
    if declared is not elected:
        raise ActividadAssetValidationError(
            context={"elected": elected.value, "declared": declared.value},
            translated_message="ledger.actividad_asset.errors.profile_modality_mismatch",
        )


__all__ = [
    "ActivityAssetFilingHandoff",
    "ActivityAssetOperations",
    "ActivityAssetRegisterAuthority",
    "M130AccrualProjection",
    "M130Contribution",
    "SupersedingClaimRequest",
]
