"""Shared application operations for IRPF activity-asset frontends.

Its pinned edition lookup returns the :class:`ModeloRevision` used by each tax-year operation.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, Field, model_validator

from ...core.casilla_id import CasillaId
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.money.rounding import round_to_cents
from ...core.period import Period
from ...core.tipos_actividad import TipoActividad
from ...domain.calculations.registry.actividad_asset_bindings import (
    ActivityAssetDisposalBounds,
    takes_used_double_coefficient,
)
from ...domain.calculations.registry.actividad_asset_form_options import activity_asset_form_options
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.errors import RegistryError
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.registry.schema_references import LegalReference, TemporalProjectionDirection
from ...domain.calculations.registry.temporal import revision_temporal_resolution
from ...domain.contribuyente.tax_residence import ResidenceTerritory
from ...domain.renta.actividad_asset.claims import (
    AmortizationClaim,
    ClaimProjection,
    amount_before_baja_zeroed,
    asset_schedule_history,
    claims_through_year,
    current_revisions,
    effective_claims,
    equal_figures_claim,
    project_m100,
    record_claim,
)
from ...domain.renta.actividad_asset.disposal import (
    ADMITTED_DISPOSAL_REASONS,
    ActivityAssetDisposal,
    ActivityAssetDisposalCalculation,
    ActivityAssetDisposalReason,
)
from ...domain.renta.actividad_asset.election import FREE_AMOUNT_METHODS, DirectEstimationRegime
from ...domain.renta.actividad_asset.election_facts import method_is_statable
from ...domain.renta.actividad_asset.errors import (
    ActividadAssetClaimConflictError,
    ActividadAssetError,
    ActividadAssetIncompleteError,
    ActividadAssetUnsupportedError,
    ActividadAssetValidationError,
)
from ...domain.renta.actividad_asset.lifecycle import REGISTERABLE_ACQUISITION_SHAPES, ActivityAssetRevision, AssetKind
from ...domain.renta.actividad_asset.register_records import ActivityAssetDescriptorFacts
from ...domain.renta.actividad_asset.schedule import (
    ScheduleAuthority,
    ScheduledAmortizationCharge,
    require_method_continuity,
)
from ..operations.public_scalar import project_scalar
from .acquisition_candidates import acquisition_candidates
from .acquisition_ledger import require_acquisition_in_ledger
from .activity_asset_read_models import (
    PLAN_ADVISORY_FAMILY,
    ActivityAssetAcquisitionCandidate,
    ActivityAssetDisposalReasonOption,
    ActivityAssetEdition,
    ActivityAssetElectionLimits,
    ActivityAssetFormOptionsView,
    ActivityAssetListRow,
    ActivityAssetNotTableBoundReason,
    ActivityAssetPlanAdvisory,
    ActivityAssetPlanAdvisoryKind,
    ActivityAssetPlanRow,
    ActivityAssetTableGroup,
    ActivityAssetTimelineEvent,
    activity_asset_label_key,
    project_reason_facts,
)
from .disposal_calculation import calculate_element_disposal
from .fact_wording import token_family
from .history import ActivityAssetHistory, ActivityAssetHistoryClaimResult
from .legal_citations import resolve_legal_citations
from .ports import (
    AcquisitionLedgerReader,
    ActivityAssetForecastOperation,
    ActivityAssetHistoryRepository,
    TaxpayerModalityReader,
)
from .register_reads import (
    RegisterReadContext,
    default_register_year,
    election_limits,
    element_list,
    element_plan,
    method_facts_view,
)
from .register_timeline import element_timeline
from .schedule_walk import (
    M100GapKind,
    M130ElementOutcome,
    error_reason_facts,
    m100_claim_gaps,
    m130_register_accruals,
)
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
    out, ``free_gap_asset_ids`` those whose method leaves an unrecorded amount to
    the taxpayer, and ``agrarian_excluded_asset_ids`` those of an agrarian activity,
    which pays a share of income, so an amount that leaves them out says so.
    """

    model_config = STRICT_FROZEN_CONFIG

    target_casilla_id: CasillaId
    tax_year: int
    amount: Decimal
    contributions: tuple[M130Contribution, ...] = ()
    unavailable_asset_ids: tuple[str, ...] = ()
    free_gap_asset_ids: tuple[str, ...] = ()
    agrarian_excluded_asset_ids: tuple[str, ...] = ()


class M100ClaimGapProjection(BaseModel):
    """An interval of the year Modelo 100 leaves out of an element, and what it would have accrued."""

    model_config = STRICT_FROZEN_CONFIG

    asset_id: str = Field(min_length=1)
    kind: M100GapKind
    covered_from: date
    covered_until: date
    accrued: Decimal | None = None


class ActivityAssetFilingHandoff(BaseModel):
    """Non-consuming projections for both supported IRPF filing destinations.

    ``m100_gaps`` says what the Modelo 100 boxes leave out because no claim records it.
    """

    model_config = STRICT_FROZEN_CONFIG

    material_m100: ClaimProjection
    intangible_m100: ClaimProjection
    m100_gaps: tuple[M100ClaimGapProjection, ...] = ()
    material_m130: M130AccrualProjection | None = None
    intangible_m130: M130AccrualProjection | None = None
    """Both set for a Modelo 130 period, and both absent when the handoff states Modelo 100 alone."""

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _m130_together(self) -> Self:
        if (self.material_m130 is None) != (self.intangible_m130 is None):
            raise ValueError("a filing handoff states the Modelo 130 accrual of both asset kinds or of neither")
        return self


class SupersedingClaimRequest(BaseModel):
    """A recorded claim a correction replaces; its interval carries over and the backend works out the figure."""

    model_config = STRICT_FROZEN_CONFIG

    supersedes_claim_id: str = Field(min_length=64, max_length=64)
    requested_free_amount: Decimal | None = None


def pinned_edition(operation: PinnedAuthorityOperation) -> Callable[[int], tuple[ActivityAssetEdition, ModeloRevision]]:
    """Read the Modelo 100 edition a tax year falls under in one authority pin, and whether it is projected."""

    def read(tax_year: int) -> tuple[ActivityAssetEdition, ModeloRevision]:
        revision = operation.revision_for_context("100", filing_year=tax_year, period="0A")
        resolution = revision_temporal_resolution(
            revision,
            filing_year=tax_year,
            period="0A",
            support=operation.supported_filing_years(),
        )
        return (
            ActivityAssetEdition(
                revision_id=revision.id,
                authored_filing_year=resolution.authored_filing_year,
                projected=resolution.projection_direction is not TemporalProjectionDirection.AUTHORED,
            ),
            revision,
        )

    return read


@dataclass(frozen=True, slots=True)
class ActivityAssetRegisterAuthority:
    """The pinned-authority and profile facts the register's reads and handoff depend on."""

    edition: Callable[[int], tuple[ActivityAssetEdition, ModeloRevision]]
    admits_filing_year: Callable[[int], bool]
    last_admitted_year: Callable[[], int]
    agrarian_activities: Callable[[date], frozenset[TipoActividad]]
    residence_territory: Callable[[date], ResidenceTerritory]
    claim_consumers: Callable[[Iterable[str]], Mapping[str, tuple[str, ...]]]
    today: Callable[[], date]
    schedule_authority: Callable[[ActivityAssetRevision, int], ScheduleAuthority]
    class_labels: Callable[[DirectEstimationRegime, int], Mapping[str, str]]
    disposal_bounds: Callable[[ActivityAssetRevision, int], ActivityAssetDisposalBounds]
    legal_reference: Callable[[str], LegalReference]
    m130_amortization_casilla: Callable[[Period], CasillaId]
    m100_amortization_casillas: Callable[[int], Mapping[AssetKind, CasillaId]]


def _year_end(tax_year: int) -> date:
    return date(tax_year, 12, 31)


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
        """Create an asset from its first immutable revision and first descriptor, in one write.

        An identical retry returns the recorded history; a differing one is refused.
        """
        if revision.revision_number != 1:
            raise ActividadAssetValidationError(
                translated_message="ledger.actividad_asset.errors.creation_requires_first_revision"
            )
        history = self._service.reopen()
        recorded = next((item for item in history.revisions if item.asset_id == revision.asset_id), None)
        if recorded is not None:
            if recorded.revision_id == revision.revision_id and any(
                item.asset_id == revision.asset_id and item.descriptor_number == 1 and item.facts == descriptor
                for item in history.descriptors
            ):
                return history
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
        baja_claims = self._changed_disposal_claims(revision, current, history, origin=origin)
        replaced = {claim.supersedes_claim_id for claim in baja_claims}
        claims = (
            *baja_claims,
            *self._superseding_claims(
                revision,
                tuple(item for item in superseding_claims if item.supersedes_claim_id not in replaced),
                history,
                origin=origin,
                starting_from=baja_claims,
            ),
        )

        def mutation(latest: ActivityAssetHistory) -> ActivityAssetHistory:
            if not latest.same_tax_facts(history):
                raise ActividadAssetClaimConflictError(
                    translated_message="ledger.actividad_asset.errors.history_changed_after_forecast",
                )
            return latest.apply_correction(revision, claims, recorded_at=recorded_at, origin=origin)

        return self._service.apply(mutation)

    def _changed_disposal_claims(
        self,
        revision: ActivityAssetRevision,
        current: ActivityAssetRevision,
        history: ActivityAssetHistory,
        *,
        origin: str | None,
    ) -> tuple[AmortizationClaim, ...]:
        if revision.disposal == current.disposal:
            return ()
        for disposal in (revision.disposal, current.disposal):
            if disposal is not None:
                self._require_common_territory(_year_end(disposal.disposal_date.year))
        return self._baja_supersessions(revision, history, origin=origin)

    def _superseding_claims(
        self,
        revision: ActivityAssetRevision,
        requests: tuple[SupersedingClaimRequest, ...],
        history: ActivityAssetHistory,
        *,
        origin: str | None,
        starting_from: tuple[AmortizationClaim, ...] = (),
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
            self._require_common_territory(_year_end(superseded.tax_year))
            targets.append((superseded, request))
        _require_profile_modality(revision.amortization.regime, self._taxpayer_modality())
        revisions = (*history.revisions, revision)
        working = (*history.claims, *starting_from)
        recorded: list[AmortizationClaim] = []
        for superseded, request in sorted(targets, key=lambda item: item[0].covered_from):
            charge = self._forecast_operation(
                revision,
                covered_from=superseded.covered_from,
                covered_until=superseded.covered_until,
                history=asset_schedule_history(
                    claims_through_year(working, superseded.tax_year),
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
            result = record_claim(working, claim)
            working = result.claims
            if not result.reused_existing_claim:
                recorded.append(claim)
        return tuple(recorded)

    def _baja_supersessions(
        self,
        revision: ActivityAssetRevision,
        history: ActivityAssetHistory,
        *,
        origin: str | None,
    ) -> tuple[AmortizationClaim, ...]:
        """Work out what a baja, or its removal or new date, replaces in one write.

        Claims after the boundary go to zero and a crossing one is shortened.  A zero
        claim an earlier baja wrote comes back inside the service window: with no
        boundary or a later one it would otherwise keep the year's deduction at zero.
        The claims after the boundary go first, so that later charges are judged
        without them, and the rest run in date order on the state the earlier ones
        leave.  A free amount is the taxpayer's election and carries over; any other
        amount is recomputed.  A shortened claim keeps its interval, because a claim
        never widens: the rest of its year reads as a gap.
        """
        disposal = revision.disposal
        boundary = None if disposal is None else disposal.boundary
        creating_operation = origin or revision.asset_id
        standing = tuple(claim for claim in effective_claims(history.claims) if claim.asset_id == revision.asset_id)
        recorded = _baja_zero_claims(standing, boundary, revision.revision_id, creating_operation)
        recompute = sorted(
            (claim for claim in standing if _baja_needs_recomputation(claim, boundary)),
            key=lambda claim: claim.covered_from,
        )
        if not recompute:
            return tuple(recorded)
        _require_profile_modality(revision.amortization.regime, self._taxpayer_modality())
        for claim in recompute:
            replacement = self._baja_recomputed_claim(
                claim,
                revision,
                (*history.claims, *recorded),
                (*history.revisions, revision),
                boundary=boundary,
                creating_operation=creating_operation,
            )
            if replacement is not None:
                recorded.append(replacement)
        return tuple(recorded)

    def _baja_recomputed_claim(
        self,
        claim: AmortizationClaim,
        revision: ActivityAssetRevision,
        working: tuple[AmortizationClaim, ...],
        revisions: tuple[ActivityAssetRevision, ...],
        *,
        boundary: date | None,
        creating_operation: str,
    ) -> AmortizationClaim | None:
        """Replace one claim under the new boundary; a zero claim stays where the schedule also charges zero."""
        crossing = boundary is not None and claim.covered_until > boundary
        free = revision.amortization.method in FREE_AMOUNT_METHODS
        charge = self._forecast_operation(
            revision,
            covered_from=claim.covered_from,
            covered_until=boundary if boundary is not None and crossing else claim.covered_until,
            history=asset_schedule_history(
                claims_through_year(working, claim.tax_year),
                revisions,
                asset_id=revision.asset_id,
                tax_year=claim.tax_year,
                excluding_claim_id=claim.claim_id,
            ),
            requested_free_amount=amount_before_baja_zeroed(claim, working) if free else None,
        )
        if not crossing and charge.amount <= Decimal("0"):
            return None
        return AmortizationClaim.from_schedule(
            charge,
            asset_kind=revision.asset_kind,
            creating_operation=creating_operation,
            supersedes_claim_id=claim.claim_id,
            disposal_revision_id=revision.revision_id if crossing else None,
        )

    def dispose(
        self,
        asset_id: str,
        disposal: ActivityAssetDisposal,
        *,
        recorded_at: datetime | None = None,
        origin: str | None = None,
    ) -> ActivityAssetHistory:
        """Record a baja and the claims it replaces in one compare-and-swap.

        A missing opening history does not stop the baja, only its calculation.  An
        identical retry returns the recorded history; otherwise a recorded baja changes
        only through a correction.
        """
        self._require_common_territory(_year_end(disposal.disposal_date.year))
        history = self._service.reopen()
        current = self.inspect(asset_id)[-1]
        if current.disposal == disposal:
            return history
        if current.disposal is not None:
            raise ActividadAssetClaimConflictError(
                context={"disposal_date": current.disposal.disposal_date.isoformat()},
                translated_message="ledger.actividad_asset.errors.disposal_already_recorded",
            )
        revision = current.with_disposal(disposal)
        claims = self._baja_supersessions(revision, history, origin=origin)

        def mutation(latest: ActivityAssetHistory) -> ActivityAssetHistory:
            if not latest.same_tax_facts(history):
                raise ActividadAssetClaimConflictError(
                    translated_message="ledger.actividad_asset.errors.history_changed_after_forecast",
                )
            return latest.apply_correction(revision, claims, recorded_at=recorded_at, origin=origin)

        return self._service.apply(mutation)

    def disposal_calculation(
        self,
        asset_id: str,
        disposal: ActivityAssetDisposal | None = None,
    ) -> tuple[ActivityAssetDisposal, ActivityAssetDisposalCalculation]:
        """Work out a baja's figures, recording nothing: the stated one as a preview, else the recorded one.

        A preview sees the history as that baja would leave it.
        """
        history = self._service.reopen()
        current = self.inspect(asset_id)[-1]
        stated = current.disposal if disposal is None else disposal
        if stated is None:
            raise ActividadAssetValidationError(
                translated_message="ledger.actividad_asset.errors.disposal_not_recorded",
            )
        self._require_common_territory(_year_end(stated.disposal_date.year))
        if disposal is None:
            return stated, self._calculate(current, stated, history)
        revision = current.with_disposal(disposal)
        if revision.opening_history.accumulated_amount is None:
            raise ActividadAssetIncompleteError(
                translated_message="ledger.actividad_asset.errors.opening_history_missing",
            )
        preview = history.apply_correction(revision, self._baja_supersessions(revision, history, origin=None))
        return disposal, self._calculate(revision, disposal, preview)

    def _calculate(
        self,
        revision: ActivityAssetRevision,
        disposal: ActivityAssetDisposal,
        history: ActivityAssetHistory,
    ) -> ActivityAssetDisposalCalculation:
        return calculate_element_disposal(revision, disposal, history, bounds=self._authority.disposal_bounds)

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
        self._require_common_territory(_year_end(covered_from.year))
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
        return self._charge_for_year(
            revision,
            history,
            covered_from=covered_from,
            covered_until=covered_until,
            requested_free_amount=requested_free_amount,
            excluding_claim_id=excluding_claim_id,
        )

    def _charge_for_year(
        self,
        revision: ActivityAssetRevision,
        history: ActivityAssetHistory,
        *,
        covered_from: date,
        covered_until: date,
        requested_free_amount: Decimal | None,
        excluding_claim_id: str | None,
    ) -> ScheduledAmortizationCharge:
        """Work out a charge as the walk does, on the claims through its year.

        A later claim moves no figure.  It can still refuse the charge outright, for a
        method whose amount follows the pending value, so that rule reads every claim.
        """
        tax_year = covered_from.year
        election = revision.amortization
        require_method_continuity(
            election.method,
            election.fingerprint,
            asset_schedule_history(
                history.claims,
                history.revisions,
                asset_id=revision.asset_id,
                tax_year=tax_year,
                excluding_claim_id=excluding_claim_id,
            ),
        )
        return self._forecast_operation(
            revision,
            covered_from=covered_from,
            covered_until=covered_until,
            history=asset_schedule_history(
                claims_through_year(history.claims, tax_year),
                history.revisions,
                asset_id=revision.asset_id,
                tax_year=tax_year,
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
        self._require_common_territory(_year_end(forecast.tax_year))
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
        if any(existing.claim_id == claim.claim_id for existing in current_history.claims) or (
            equal_figures_claim(current_history.claims, claim) is not None
        ):
            return self._service.record_claim(claim)
        last_admitted_year = self._authority.last_admitted_year()
        if forecast.tax_year > last_admitted_year:
            raise ActividadAssetUnsupportedError(
                context={"tax_year": forecast.tax_year, "last_admitted_year": last_admitted_year},
                translated_message="ledger.actividad_asset.errors.claim_year_beyond_registry",
            )
        _require_profile_modality(revision.amortization.regime, self._taxpayer_modality())
        recomputed = self._charge_for_year(
            revision,
            current_history,
            covered_from=forecast.covered_from,
            covered_until=forecast.covered_until,
            requested_free_amount=(forecast.amount if forecast.method in FREE_AMOUNT_METHODS else None),
            excluding_claim_id=supersedes_claim_id,
        )
        if recomputed != forecast:
            raise ActividadAssetValidationError(
                translated_message="ledger.actividad_asset.errors.forecast_no_longer_matches"
            )
        return self._service.record_claim(claim, expected_history=current_history, recorded_at=recorded_at)

    def filing_handoff(self, *, tax_year: int, m130_period: Period | None = None) -> ActivityAssetFilingHandoff:
        """Project M100 from effective claims and, for a stated period, M130 from the accrual route.

        Without ``m130_period`` only the Modelo 100 boxes are projected; no Modelo 130 figure is
        worked out. Nothing is recorded.
        """
        history = self._service.reopen()
        if history.revisions:
            self._require_common_territory(_year_end(tax_year))
            if m130_period is not None:
                self._require_common_territory(m130_period.end_date)
        m100_boxes = self._authority.m100_amortization_casillas(tax_year)

        def m100(asset_kind: AssetKind) -> ClaimProjection:
            box = m100_boxes.get(asset_kind)
            if box is None:
                raise ActividadAssetUnsupportedError(
                    context={"asset_kind": asset_kind.value, "tax_year": tax_year},
                    translated_message="ledger.actividad_asset.errors.amortization_box_not_bound",
                )
            return project_m100(history.claims, asset_kind=asset_kind, tax_year=tax_year, target_casilla_id=box)

        material_m100 = m100(AssetKind.MATERIAL)
        intangible_m100 = m100(AssetKind.INTANGIBLE)
        m100_gaps = tuple(
            M100ClaimGapProjection(
                asset_id=gap.revision.asset_id,
                kind=gap.kind,
                covered_from=gap.covered_from,
                covered_until=gap.covered_until,
                accrued=gap.accrued,
            )
            for revision in current_revisions(history.revisions).values()
            for gap in m100_claim_gaps(revision, history, forecast=self._forecast_operation, tax_year=tax_year)
        )
        if m130_period is None:
            return ActivityAssetFilingHandoff(
                material_m100=material_m100, intangible_m100=intangible_m100, m100_gaps=m100_gaps
            )
        period_end = m130_period.end_date
        current = {revision.asset_id: revision for revision in history.revisions}
        rows = self._ledger.load_by_ids(
            {owned for revision in current.values() for owned in revision.acquisition_transaction_ids},
        ).transactions
        accruals = m130_register_accruals(
            history,
            forecast=self._forecast_operation,
            period_end=period_end,
            activities={asset_id: revision.activity_in(rows) for asset_id, revision in current.items()},
            agrarian=self._authority.agrarian_activities(period_end) if current else frozenset(),
        )

        m130_box = self._authority.m130_amortization_casilla(m130_period)

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
                target_casilla_id=m130_box,
                tax_year=tax_year,
                amount=round_to_cents(sum((item.amount for item in contributions), Decimal("0"))),
                contributions=contributions,
                unavailable_asset_ids=tuple(
                    accrual.revision.asset_id
                    for accrual in selected
                    if accrual.outcome is M130ElementOutcome.UNAVAILABLE
                ),
                free_gap_asset_ids=tuple(
                    accrual.revision.asset_id for accrual in selected if accrual.outcome is M130ElementOutcome.FREE_GAP
                ),
                agrarian_excluded_asset_ids=tuple(
                    accrual.revision.asset_id
                    for accrual in selected
                    if accrual.outcome is M130ElementOutcome.AGRARIAN_EXCLUDED
                ),
            )

        return ActivityAssetFilingHandoff(
            material_m100=material_m100,
            intangible_m100=intangible_m100,
            m100_gaps=m100_gaps,
            material_m130=m130(AssetKind.MATERIAL),
            intangible_m130=m130(AssetKind.INTANGIBLE),
        )

    def _require_common_territory(self, period_end: date) -> None:
        """Refuse a write for a period the residence places in a foral territory, or an unreadable residence.

        It reads the residence in force at the end of the period written, as the
        calculation of that period does, so a later move does not reach back and an
        unrecorded period does not refuse.
        """
        territory = self._authority.residence_territory(period_end)
        if territory is ResidenceTerritory.FORAL:
            raise ActividadAssetValidationError(translated_message="ledger.actividad_asset.errors.foral_territory")
        if territory is ResidenceTerritory.UNRESOLVED:
            raise ActividadAssetValidationError(
                translated_message="ledger.actividad_asset.errors.tax_residence_unresolved",
            )

    def _read_context(self, history: ActivityAssetHistory) -> RegisterReadContext:
        return RegisterReadContext(
            history=history,
            forecast=self._forecast_operation,
            edition=lambda tax_year: self._authority.edition(tax_year)[0],
            admits_filing_year=self._authority.admits_filing_year,
            last_admitted_year=self._authority.last_admitted_year(),
            today=self._authority.today(),
            minimum_bounds=self._authority.disposal_bounds,
            class_labels=self._authority.class_labels,
        )

    def list_elements(self) -> tuple[ActivityAssetListRow, ...]:
        """Summarise every element of the register."""
        return element_list(self._read_context(self._service.reopen()))

    def default_register_year(self, years: Iterable[int]) -> int | None:
        """Name the year the register opens on, by this register's clock."""
        return default_register_year(years, today=self._authority.today())

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
            schedule = self._authority.schedule_authority(revision, tax_year)
            return election_limits(
                revision,
                schedule,
                activity_asset_form_options(
                    modelo,
                    tax_year=tax_year,
                    asset_kind=revision.asset_kind,
                    regime=revision.amortization.regime,
                    class_labels=self._authority.class_labels(revision.amortization.regime, tax_year),
                ),
                resolve_legal_citations(
                    schedule.source_reference.split(";"),
                    modelo=modelo,
                    legal_reference=self._authority.legal_reference,
                ),
            )
        except RegistryError:
            reason_key = "ledger.actividad_asset.errors.tax_year_without_edition"
            reason_facts = {"tax_year": str(tax_year)}
        except ActividadAssetError as error:
            reason_key = error.translated_message
            reason_facts = error_reason_facts(error)
        return ActivityAssetElectionLimits(
            class_key=revision.amortization.authority_class_key,
            not_table_bound=ActivityAssetNotTableBoundReason.AUTHORITY_UNAVAILABLE,
            unavailable_reason_key=reason_key,
            unavailable_reason_facts=project_reason_facts(reason_facts),
        )

    def plan_advisories(self, asset_id: str) -> tuple[ActivityAssetPlanAdvisory, ...]:
        """Say what the plan warns about the element's election, under this year's edition.

        A warning looks only at the election and changes no figure.  Without an edition
        there is no charge for it to speak about.
        """
        revision = self.inspect(asset_id)[-1]
        tax_year = max(self._authority.today().year, revision.in_service_date.year)
        try:
            _, modelo = self._authority.edition(tax_year)
        except RegistryError:
            return ()
        if not takes_used_double_coefficient(modelo, tax_year=tax_year, asset_revision=revision):
            return ()
        kind = ActivityAssetPlanAdvisoryKind.USED_ELEMENT_GROUP_LIMIT
        return (ActivityAssetPlanAdvisory(kind=kind, label_key=activity_asset_label_key(PLAN_ADVISORY_FAMILY, kind)),)

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
        options = activity_asset_form_options(
            revision,
            tax_year=tax_year,
            asset_kind=asset_kind,
            regime=regime,
            class_labels=self._authority.class_labels(regime, tax_year),
        )
        offered = tuple(method for method in options.methods if method_is_statable(method))
        return ActivityAssetFormOptionsView(
            tax_year=tax_year,
            asset_kind=asset_kind,
            regime=regime,
            edition=edition,
            acquisition_shapes=REGISTERABLE_ACQUISITION_SHAPES,
            declared_activities=tuple(TipoActividad),
            methods=offered,
            method_facts=tuple(method_facts_view(method) for method in offered),
            table_groups=tuple(
                ActivityAssetTableGroup(
                    class_key=group.class_key,
                    class_label=group.class_label,
                    maximum_coefficient=project_scalar(group.maximum_coefficient),
                    minimum_coefficient=project_scalar(group.minimum_coefficient),
                    maximum_period_years=project_scalar(group.maximum_period_years),
                    can_hold_vehicle=group.can_hold_vehicle,
                )
                for group in options.table_groups
            ),
            disposal_reasons=tuple(
                ActivityAssetDisposalReasonOption(
                    reason=reason,
                    label_key=activity_asset_label_key(token_family(ActivityAssetDisposalReason), reason),
                )
                for reason in ADMITTED_DISPOSAL_REASONS
            ),
        )

    def acquisition_candidates(self) -> tuple[ActivityAssetAcquisitionCandidate, ...]:
        """List the business payments no element names as its acquisition yet."""
        return acquisition_candidates(self._ledger.load(), self._service.reopen())


def _baja_zero_claims(
    claims: tuple[AmortizationClaim, ...], boundary: date | None, revision_id: str, creating_operation: str
) -> list[AmortizationClaim]:
    if boundary is None:
        return []
    return [
        claim.set_to_zero_by_baja(revision_id, creating_operation=creating_operation)
        for claim in claims
        if claim.covered_from >= boundary and claim.amount > Decimal("0")
    ]


def _baja_needs_recomputation(claim: AmortizationClaim, boundary: date | None) -> bool:
    crossing = boundary is not None and claim.covered_from < boundary < claim.covered_until
    restored = (
        claim.disposal_revision_id is not None
        and claim.amount == Decimal("0")
        and (boundary is None or claim.covered_until <= boundary)
    )
    return crossing or restored


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
    "M100ClaimGapProjection",
    "M130AccrualProjection",
    "M130Contribution",
    "SupersedingClaimRequest",
]
