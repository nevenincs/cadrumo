"""Safe frontend-neutral full-calendar projection for Declarations.

The projector accepts an already-built legal calendar and the already-built
calendar-evidence projection.  It performs no reads.  Protected work, filing,
calculation, snapshot, CSV, AEAT-reference, event-prose, and URL fields are
deliberately absent from the output model.
"""

from __future__ import annotations

from dataclasses import dataclass
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
    OverviewCalendarEntry,
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


@dataclass(frozen=True, slots=True)
class _PreparedCalendarInputs:
    """Validated authorities and observability for one calendar projection."""

    schedule_observation: DeclarationsCalendarSourceObservationV1
    local_observation: DeclarationsCalendarSourceObservationV1
    aeat_observation: DeclarationsCalendarSourceObservationV1
    evidence_by_address: dict[tuple[str, int, str], OverviewCalendarFilingEvidence]
    schedule_observable: bool
    local_observable: bool
    aeat_observable: bool


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

    @model_validator(mode="after")
    def _recovery_action_is_the_canonical_create_at_this_address(self) -> Self:
        """A recovery action must be the create action, bound to THIS entry.

        The rule lived in the projector and again in the TUI controller, which
        left it enforced twice for projections built through the projector and
        not at all for one constructed directly -- and a frontend takes the
        model, not the projector. Carrying it here makes construction the
        moment it is checked, which is the only moment every caller shares.

        The bindings half matters as much as the action id: an action naming
        the right operation against a DIFFERENT address would offer the
        operator a recovery that silently creates the wrong obligation.
        """
        if self.recovery_action is None:
            return self
        if self.recovery_action.action.action_id != "operator.modelo.work.create":
            raise ValueError("calendar recovery action is not the canonical create action")
        bindings = {item.argument_name: item.value for item in self.recovery_action.argument_bindings}
        if bindings != {
            "modelo": str(self.modelo),
            "year": self.filing_year,
            "period": self.period.registry_token,
        }:
            raise ValueError("calendar recovery action contradicts its natural address")
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
        _validate_projection_model(self)
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
    prepared = _prepare_calendar_inputs(calendar=calendar, evidence=evidence, schedule_observation=schedule_observation)
    rows = _project_calendar_rows(calendar.entries, prepared)
    sources = _project_calendar_sources(evidence.evidence, rows, prepared)
    return DeclarationsCalendarProjectionV1(
        as_of=as_of,
        generated_at=calendar.generated_at,
        query_range=calendar.range,
        sources=sources,
        entries=tuple(rows),
    )


def _prepare_calendar_inputs(
    *,
    calendar: OverviewCalendar,
    evidence: CalendarEvidenceProjection,
    schedule_observation: DeclarationsCalendarSourceObservationV1,
) -> _PreparedCalendarInputs:
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
    _validate_unobservable_evidence(
        evidence.evidence,
        local_observable=local_observable,
        aeat_observable=aeat_observable,
    )

    schedule_addresses = _schedule_addresses(calendar.entries)
    if set(evidence_by_address).difference(schedule_addresses):
        raise DeclarationsCalendarProjectionError("calendar evidence has no scheduled natural address")
    return _PreparedCalendarInputs(
        schedule_observation=schedule_observation,
        local_observation=local_observation,
        aeat_observation=aeat_observation,
        evidence_by_address=evidence_by_address,
        schedule_observable=schedule_observable,
        local_observable=local_observable,
        aeat_observable=aeat_observable,
    )


def _schedule_addresses(entries: tuple[OverviewCalendarEntry, ...]) -> set[tuple[str, int, str]]:
    addresses: set[tuple[str, int, str]] = set()
    for entry in entries:
        if entry.filing_year != entry.period.filing_year:
            raise DeclarationsCalendarProjectionError("calendar entry filing year contradicts its period")
        addresses.add(_calendar_entry_address(entry))
    return addresses


def _calendar_entry_address(entry: OverviewCalendarEntry) -> tuple[str, int, str]:
    return (entry.modelo, entry.period.filing_year, entry.period.registry_token)


def _validate_unobservable_evidence(
    rows: tuple[OverviewCalendarFilingEvidence, ...],
    *,
    local_observable: bool,
    aeat_observable: bool,
) -> None:
    if not local_observable and any(
        row.local_filing_state is not OverviewLocalFilingState.NOT_READY_TO_FILE for row in rows
    ):
        raise DeclarationsCalendarProjectionError("unobservable local evidence carries a confident claim")
    if not aeat_observable and any(
        row.aeat_submission_state is not OverviewAeatSubmissionState.NOT_OBSERVED or row.justificante_verified
        for row in rows
    ):
        raise DeclarationsCalendarProjectionError("unobservable AEAT evidence carries a confident claim")


def _project_calendar_rows(
    entries: tuple[OverviewCalendarEntry, ...],
    prepared: _PreparedCalendarInputs,
) -> list[DeclarationsCalendarEntryRefV1]:
    rows = [_project_calendar_row(entry, prepared) for entry in entries]
    rows.sort(key=lambda row: (row.adjusted_closes_on, *row.semantic_key()))
    keys = tuple(row.semantic_key() for row in rows)
    if len(keys) != len(set(keys)):
        raise DeclarationsCalendarProjectionError("calendar contains duplicate natural legal identities")
    return rows


def _project_calendar_row(
    entry: OverviewCalendarEntry,
    prepared: _PreparedCalendarInputs,
) -> DeclarationsCalendarEntryRefV1:
    key = _calendar_entry_address(entry)
    authority = prepared.evidence_by_address.get(key) or OverviewCalendarFilingEvidence(
        modelo=entry.modelo,
        filing_year=entry.period.filing_year,
        period=entry.period,
    )
    _validate_calendar_evidence_join(
        entry=entry.filing_evidence,
        authority=authority,
        local_observable=prepared.local_observable,
        aeat_observable=prepared.aeat_observable,
    )
    _validate_recovery_action(entry.recovery_action, key)
    local_filing_state, aeat_submission_state, justificante_verified = _projected_evidence_axes(
        authority,
        local_observable=prepared.local_observable,
        aeat_observable=prepared.aeat_observable,
    )
    return DeclarationsCalendarEntryRefV1(
        modelo=ModeloCode(entry.modelo),
        filing_year=entry.period.filing_year,
        period=entry.period,
        opens_on=entry.opens_on,
        adjusted_closes_on=entry.adjusted_closes_on,
        payment_cutoff_on=entry.payment_cutoff_on,
        legal_status=entry.status,
        user_state=entry.user_state,
        local_filing_state=local_filing_state,
        aeat_submission_state=aeat_submission_state,
        justificante_verified=justificante_verified,
        source=entry.source,
        recovery_action=entry.recovery_action,
    )


def _projected_evidence_axes(
    authority: OverviewCalendarFilingEvidence,
    *,
    local_observable: bool,
    aeat_observable: bool,
) -> tuple[
    OverviewLocalFilingState | None,
    OverviewAeatSubmissionState | None,
    bool | None,
]:
    local_filing_state = authority.local_filing_state if local_observable else None
    if aeat_observable:
        aeat_submission_state = authority.aeat_submission_state
        justificante_verified = authority.justificante_verified
    else:
        aeat_submission_state = None
        justificante_verified = None
    return local_filing_state, aeat_submission_state, justificante_verified


def _project_calendar_sources(
    evidence: tuple[OverviewCalendarFilingEvidence, ...],
    rows: list[DeclarationsCalendarEntryRefV1],
    prepared: _PreparedCalendarInputs,
) -> tuple[DeclarationsCalendarSourceStateV1, ...]:
    local_count = sum(item.local_filing_state is not OverviewLocalFilingState.NOT_READY_TO_FILE for item in evidence)
    aeat_count = sum(item.aeat_submission_state is not OverviewAeatSubmissionState.NOT_OBSERVED for item in evidence)
    return (
        _state(prepared.schedule_observation, len(rows) if prepared.schedule_observable else None),
        _state(prepared.local_observation, local_count if prepared.local_observable else None),
        _state(prepared.aeat_observation, aeat_count if prepared.aeat_observable else None),
    )


def _validate_projection_model(projection: DeclarationsCalendarProjectionV1) -> None:
    if projection.contract_version != DECLARATIONS_CALENDAR_CONTRACT_VERSION:
        raise ValueError("unsupported Declarations calendar contract version")
    _validate_source_order(projection.sources)
    if not projection.query_range.covers(projection.as_of):
        raise ValueError("calendar as_of must fall inside its query range")
    _validate_unique_projection_entries(projection.entries)
    by_source = {item.source: item for item in projection.sources}
    _validate_schedule_projection_count(by_source[DeclarationsCalendarSource.SCHEDULE], len(projection.entries))
    _validate_local_projection_rows(by_source[DeclarationsCalendarSource.LOCAL_FILING], projection.entries)
    _validate_aeat_projection_rows(by_source[DeclarationsCalendarSource.AEAT_EVIDENCE], projection.entries)


def _validate_source_order(sources: tuple[DeclarationsCalendarSourceStateV1, ...]) -> None:
    if tuple(item.source for item in sources) != tuple(DeclarationsCalendarSource):
        raise ValueError("calendar sources must be total and canonically ordered")


def _validate_unique_projection_entries(entries: tuple[DeclarationsCalendarEntryRefV1, ...]) -> None:
    keys = tuple(item.semantic_key() for item in entries)
    if len(keys) != len(set(keys)):
        raise ValueError("calendar entries require unique natural legal identities")


def _validate_schedule_projection_count(
    schedule: DeclarationsCalendarSourceStateV1,
    entry_count: int,
) -> None:
    if schedule.item_count is not None and schedule.item_count != entry_count:
        raise ValueError("calendar schedule count must equal its projected rows")


def _validate_local_projection_rows(
    local: DeclarationsCalendarSourceStateV1,
    entries: tuple[DeclarationsCalendarEntryRefV1, ...],
) -> None:
    if entries and _observable(local.availability) != all(row.local_filing_state is not None for row in entries):
        raise ValueError("calendar rows contradict local source observability")


def _validate_aeat_projection_rows(
    aeat: DeclarationsCalendarSourceStateV1,
    entries: tuple[DeclarationsCalendarEntryRefV1, ...],
) -> None:
    if entries and _observable(aeat.availability) != all(
        row.aeat_submission_state is not None and row.justificante_verified is not None for row in entries
    ):
        raise ValueError("calendar rows contradict AEAT source observability")


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
