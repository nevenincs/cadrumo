"""Safe frontend-neutral full-calendar projection for Declarations.

The projector accepts an already-built legal calendar and the already-built
calendar-evidence projection.  It performs no reads.  Protected work, filing,
calculation, snapshot, CSV, AEAT-reference, event-prose, and URL fields are
deliberately absent from the output model.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Final, Self

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from ...core.filing_year import FilingYear
from ...core.identifier_grammar import NamespacedId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...domain.deadlines.models import ObligationStatus
from ...domain.modelos.codes import ModeloCode
from ..operator_actions.models import DeclaredNextAction
from ..overview.calendar_models import (
    OverviewAeatSubmissionState,
    OverviewCalendar,
    OverviewCalendarEntrySource,
    OverviewCalendarFilingEvidence,
    OverviewCalendarRange,
    OverviewLocalFilingState,
    OverviewPeriodState,
)
from ..overview.evidence import CalendarEvidenceProjection
from ..overview.home import HomeAvailability, HomeZoneState

DECLARATIONS_CALENDAR_CONTRACT_VERSION: Final[int] = 1


class DeclarationsCalendarProjectionError(ValueError):
    """The supplied calendar authorities cannot form one coherent safe view."""


class DeclarationsCalendarSource(StrEnum):
    """Independent authorities retained by the calendar projection."""

    SCHEDULE = "schedule"
    LOCAL_FILING = "local.filing"
    AEAT_EVIDENCE = "aeat.evidence"


class DeclarationsCalendarSourceObservationV1(BaseModel):
    """Explicit availability and freshness for one source authority."""

    model_config = STRICT_FROZEN_CONFIG

    source: DeclarationsCalendarSource
    availability: HomeAvailability
    observed_at: datetime | None = None
    reason_code: NamespacedId | None = None

    @model_validator(mode="after")
    def _availability_is_truthful(self) -> Self:
        if self.availability is HomeAvailability.AVAILABLE and self.reason_code is not None:
            raise ValueError("an available calendar source cannot carry a refusal reason")
        if self.availability is not HomeAvailability.AVAILABLE and self.reason_code is None:
            raise ValueError("a non-available calendar source requires a refusal reason")
        if self.availability is HomeAvailability.STALE and self.observed_at is None:
            raise ValueError("a stale calendar source requires its last observation time")
        if self.availability is HomeAvailability.NEVER_CAPTURED and self.observed_at is not None:
            raise ValueError("a never-captured calendar source cannot carry an observation time")
        return self


class DeclarationsCalendarSourceStateV1(DeclarationsCalendarSourceObservationV1):
    """One source observation plus measured cardinality when observable."""

    item_count: NonNegativeInt | None = None

    @model_validator(mode="after")
    def _count_matches_observability(self) -> Self:
        observable = self.availability in {HomeAvailability.AVAILABLE, HomeAvailability.STALE}
        if observable != (self.item_count is not None):
            raise ValueError("only observable calendar sources carry a measured count")
        return self


class DeclarationsCalendarEntryRefV1(BaseModel):
    """Safe legal natural identity and independent calendar state axes."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: ModeloCode
    filing_year: FilingYear
    period: Period
    opens_on: date
    adjusted_closes_on: date
    payment_cutoff_on: date | None = None
    legal_status: ObligationStatus
    user_state: OverviewPeriodState
    local_filing_state: OverviewLocalFilingState | None
    aeat_submission_state: OverviewAeatSubmissionState | None
    justificante_verified: bool | None
    source: OverviewCalendarEntrySource
    recovery_action: DeclaredNextAction | None = Field(default=None, exclude=True, repr=False)

    @model_validator(mode="after")
    def _safe_axes_are_coherent(self) -> Self:
        if self.period.filing_year != self.filing_year:
            raise ValueError("calendar natural address year and period disagree")
        if self.opens_on > self.adjusted_closes_on:
            raise ValueError("calendar opening cannot follow its adjusted close")
        if self.payment_cutoff_on is not None and self.payment_cutoff_on > self.adjusted_closes_on:
            raise ValueError("calendar payment cutoff cannot follow its adjusted close")
        expected_user_state = {
            ObligationStatus.UPCOMING: OverviewPeriodState.DUE,
            ObligationStatus.DUE_SOON: OverviewPeriodState.DUE,
            ObligationStatus.DUE_TODAY: OverviewPeriodState.DUE,
            ObligationStatus.OVERDUE: OverviewPeriodState.LATE,
            ObligationStatus.FILED: OverviewPeriodState.FILED,
            ObligationStatus.NOT_APPLICABLE: OverviewPeriodState.UNKNOWN,
        }[self.legal_status]
        if self.user_state is not expected_user_state:
            raise ValueError("calendar legal status and user state disagree")
        if self.aeat_submission_state is None:
            if self.justificante_verified is not None:
                raise ValueError("unknown AEAT evidence cannot carry justificante certainty")
        elif (self.aeat_submission_state is OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED) != (
            self.justificante_verified is True
        ):
            raise ValueError("AEAT justificante state and verification flag disagree")
        return self

    def semantic_key(self) -> tuple[str, int, str]:
        """Return the public natural obligation identity."""
        return (str(self.modelo), self.filing_year, self.period.registry_token)


class DeclarationsCalendarProjectionV1(BaseModel):
    """Immutable safe full calendar suitable for a frontend."""

    model_config = STRICT_FROZEN_CONFIG

    contract_version: int = DECLARATIONS_CALENDAR_CONTRACT_VERSION
    as_of: date
    generated_at: datetime
    query_range: OverviewCalendarRange
    sources: tuple[DeclarationsCalendarSourceStateV1, ...]
    entries: tuple[DeclarationsCalendarEntryRefV1, ...]

    @model_validator(mode="after")
    def _sources_are_total_and_entries_unique(self) -> Self:
        if self.contract_version != DECLARATIONS_CALENDAR_CONTRACT_VERSION:
            raise ValueError("unsupported Declarations calendar contract version")
        if tuple(item.source for item in self.sources) != tuple(DeclarationsCalendarSource):
            raise ValueError("calendar sources must be total and canonically ordered")
        if not self.query_range.covers(self.as_of):
            raise ValueError("calendar as_of must fall inside its query range")
        keys = tuple(item.semantic_key() for item in self.entries)
        if len(keys) != len(set(keys)):
            raise ValueError("calendar entries require unique natural legal identities")
        by_source = {item.source: item for item in self.sources}
        schedule = by_source[DeclarationsCalendarSource.SCHEDULE]
        local = by_source[DeclarationsCalendarSource.LOCAL_FILING]
        aeat = by_source[DeclarationsCalendarSource.AEAT_EVIDENCE]
        if schedule.item_count is not None and schedule.item_count != len(self.entries):
            raise ValueError("calendar schedule count must equal its projected rows")
        if (
            _observable(local.availability) != all(row.local_filing_state is not None for row in self.entries)
            and self.entries
        ):
            raise ValueError("calendar rows contradict local source observability")
        if (
            _observable(aeat.availability)
            != all(
                row.aeat_submission_state is not None and row.justificante_verified is not None for row in self.entries
            )
            and self.entries
        ):
            raise ValueError("calendar rows contradict AEAT source observability")
        return self


def project_declarations_calendar(
    *,
    calendar: OverviewCalendar,
    evidence: CalendarEvidenceProjection,
    as_of: date,
    schedule_observation: DeclarationsCalendarSourceObservationV1,
) -> DeclarationsCalendarProjectionV1:
    """Join already-built calendar authorities into one deadline projection.

    Not "redacted": this projection's subject is dates, legal windows and
    observation states, and it carries all of them. It withholds nothing the
    operator is entitled to; there is simply no monetary fact in a calendar.
    """
    if schedule_observation.source is not DeclarationsCalendarSource.SCHEDULE:
        raise DeclarationsCalendarProjectionError("schedule observation names another calendar source")
    schedule_observable = _observable(schedule_observation.availability)
    if not schedule_observable and calendar.entries:
        raise DeclarationsCalendarProjectionError("an unavailable schedule cannot carry legal rows")

    local_observation = _observation_from_home(DeclarationsCalendarSource.LOCAL_FILING, evidence.local_state)
    aeat_observation = _observation_from_home(DeclarationsCalendarSource.AEAT_EVIDENCE, evidence.aeat_state)
    evidence_by_address = _evidence_by_address(evidence.evidence)
    local_observable = _observable(local_observation.availability)
    aeat_observable = _observable(aeat_observation.availability)
    if not local_observable and any(
        row.local_filing_state is not OverviewLocalFilingState.NOT_READY_TO_FILE for row in evidence.evidence
    ):
        raise DeclarationsCalendarProjectionError("unobservable local evidence carries a confident claim")
    if not aeat_observable and any(
        row.aeat_submission_state is not OverviewAeatSubmissionState.NOT_OBSERVED or row.justificante_verified
        for row in evidence.evidence
    ):
        raise DeclarationsCalendarProjectionError("unobservable AEAT evidence carries a confident claim")

    schedule_addresses: set[tuple[str, int, str]] = set()
    for entry in calendar.entries:
        if entry.filing_year != entry.period.filing_year:
            raise DeclarationsCalendarProjectionError("calendar entry filing year contradicts its period")
        schedule_addresses.add((entry.modelo, entry.period.filing_year, entry.period.registry_token))
    orphaned_evidence = set(evidence_by_address).difference(schedule_addresses)
    if orphaned_evidence:
        raise DeclarationsCalendarProjectionError("calendar evidence has no scheduled natural address")

    rows: list[DeclarationsCalendarEntryRefV1] = []
    for entry in calendar.entries:
        key = (entry.modelo, entry.period.filing_year, entry.period.registry_token)
        authority = evidence_by_address.get(key) or OverviewCalendarFilingEvidence(
            modelo=entry.modelo,
            filing_year=entry.period.filing_year,
            period=entry.period,
        )
        _validate_calendar_evidence_join(
            entry=entry.filing_evidence,
            authority=authority,
            local_observable=local_observable,
            aeat_observable=aeat_observable,
        )
        _validate_recovery_action(entry.recovery_action, key)
        rows.append(
            DeclarationsCalendarEntryRefV1(
                modelo=ModeloCode(entry.modelo),
                filing_year=entry.period.filing_year,
                period=entry.period,
                opens_on=entry.opens_on,
                adjusted_closes_on=entry.adjusted_closes_on,
                payment_cutoff_on=entry.payment_cutoff_on,
                legal_status=entry.status,
                user_state=entry.user_state,
                local_filing_state=authority.local_filing_state if local_observable else None,
                aeat_submission_state=authority.aeat_submission_state if aeat_observable else None,
                justificante_verified=authority.justificante_verified if aeat_observable else None,
                source=entry.source,
                recovery_action=entry.recovery_action,
            )
        )
    rows.sort(key=lambda row: (row.adjusted_closes_on, *row.semantic_key()))
    keys = tuple(row.semantic_key() for row in rows)
    if len(keys) != len(set(keys)):
        raise DeclarationsCalendarProjectionError("calendar contains duplicate natural legal identities")

    local_count = sum(
        item.local_filing_state is not OverviewLocalFilingState.NOT_READY_TO_FILE for item in evidence.evidence
    )
    aeat_count = sum(
        item.aeat_submission_state is not OverviewAeatSubmissionState.NOT_OBSERVED for item in evidence.evidence
    )
    sources = (
        _state(schedule_observation, len(rows) if schedule_observable else None),
        _state(local_observation, local_count if local_observable else None),
        _state(aeat_observation, aeat_count if aeat_observable else None),
    )
    return DeclarationsCalendarProjectionV1(
        as_of=as_of,
        generated_at=calendar.generated_at,
        query_range=calendar.range,
        sources=sources,
        entries=tuple(rows),
    )


def _observable(availability: HomeAvailability) -> bool:
    return availability in {HomeAvailability.AVAILABLE, HomeAvailability.STALE}


def _observation_from_home(
    source: DeclarationsCalendarSource,
    state: HomeZoneState,
) -> DeclarationsCalendarSourceObservationV1:
    return DeclarationsCalendarSourceObservationV1(
        source=source,
        availability=state.availability,
        observed_at=state.observed_at,
        reason_code=state.reason_code,
    )


def _state(
    observation: DeclarationsCalendarSourceObservationV1,
    count: int | None,
) -> DeclarationsCalendarSourceStateV1:
    return DeclarationsCalendarSourceStateV1(**observation.model_dump(), item_count=count)


def _evidence_by_address(
    rows: tuple[OverviewCalendarFilingEvidence, ...],
) -> dict[tuple[str, int, str], OverviewCalendarFilingEvidence]:
    result: dict[tuple[str, int, str], OverviewCalendarFilingEvidence] = {}
    for row in rows:
        if row.modelo is None or row.filing_year is None or row.period is None:
            raise DeclarationsCalendarProjectionError("calendar evidence requires a complete natural address")
        if row.filing_year != row.period.filing_year:
            raise DeclarationsCalendarProjectionError("calendar evidence filing year contradicts its period")
        key = (row.modelo, row.filing_year, row.period.registry_token)
        if key in result:
            raise DeclarationsCalendarProjectionError("calendar evidence contains duplicate natural addresses")
        result[key] = row
    return result


def _validate_calendar_evidence_join(
    *,
    entry: OverviewCalendarFilingEvidence,
    authority: OverviewCalendarFilingEvidence,
    local_observable: bool,
    aeat_observable: bool,
) -> None:
    if local_observable:
        if entry.local_filing_state is not authority.local_filing_state:
            raise DeclarationsCalendarProjectionError("calendar and local filing authority disagree")
    elif entry.local_filing_state is not OverviewLocalFilingState.NOT_READY_TO_FILE:
        raise DeclarationsCalendarProjectionError("an unobservable local axis carries a confident filing claim")
    if aeat_observable:
        if (
            entry.aeat_submission_state is not authority.aeat_submission_state
            or entry.justificante_verified != authority.justificante_verified
        ):
            raise DeclarationsCalendarProjectionError("calendar and AEAT evidence authority disagree")
    elif entry.aeat_submission_state is not OverviewAeatSubmissionState.NOT_OBSERVED or entry.justificante_verified:
        raise DeclarationsCalendarProjectionError("an unobservable AEAT axis carries a confident evidence claim")


def _validate_recovery_action(
    action: DeclaredNextAction | None,
    address: tuple[str, int, str],
) -> None:
    if action is None:
        return
    if action.action.action_id != "operator.modelo.work.create":
        raise DeclarationsCalendarProjectionError("calendar recovery action is not the canonical create action")
    bindings = {binding.argument_name: binding.value for binding in action.argument_bindings}
    expected = {"modelo": address[0], "year": address[1], "period": address[2]}
    if bindings != expected:
        raise DeclarationsCalendarProjectionError("calendar recovery action contradicts its natural address")


__all__ = [
    "DECLARATIONS_CALENDAR_CONTRACT_VERSION",
    "DeclarationsCalendarEntryRefV1",
    "DeclarationsCalendarProjectionError",
    "DeclarationsCalendarProjectionV1",
    "DeclarationsCalendarSource",
    "DeclarationsCalendarSourceObservationV1",
    "DeclarationsCalendarSourceStateV1",
    "project_declarations_calendar",
]
