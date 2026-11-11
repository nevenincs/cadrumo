"""Calendar aggregation and evidence merge for the overview read model.

The facade composes a :class:`~cadrumo.domain.deadlines.models.Schedule` from
:class:`~cadrumo.domain.deadlines.models.TaxpayerProfile` facts and projects
already-loaded local state into :class:`OverviewCalendar` DTOs. Legal
obligation rows come from the deadline engine; observed
:class:`OverviewCalendarEvent` rows and :class:`OverviewCalendarFilingEvidence`
rows come from persisted Modelo records, local live-read snapshots, and
loaded justificante metadata supplied by the caller.

This module is local-only and pure with respect to I/O: it never starts a
live AEAT read and never verifies a justificante by fetching external
state. It only reconciles evidence the storage or CLI layer has already
loaded, preserving distinct :class:`OverviewLocalFilingState` and
:class:`OverviewAeatSubmissionState` axes.

See Also:
    :mod:`cadrumo.application.overview.calendar_models`
        Defines the calendar DTOs returned by these builders.
    :class:`~cadrumo.domain.deadlines.engine.DeadlineEngine`
        Deadline authority that produces the legal obligation schedule merged
        into the overview calendar.
    :func:`~cadrumo.application.overview.calendar_evidence.calendar_filing_evidence_from_sources`
        Pure evidence merge for local filing records, live captures,
        filed-declaration observations, and loaded justificante metadata.
    :class:`~cadrumo.application.live.justificante.JustificanteCaptureSnapshot`
        Persisted live justificante capture projected as AEAT-side evidence
        only when matching metadata is already loaded.
    :class:`~ModeloRecord`
        Local filing record projected on the local filing axis, separate from
        AEAT submission state.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import TYPE_CHECKING

from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...core.logging import get_logger
from ...core.modelo import Modelo
from ...core.time.clock import now
from ...domain.calculations.registry.applicability import derive_modelo_applicability, taxpayer_model_is_declared
from ...domain.calculations.registry.applicability_models import ApplicabilityVerdict
from ...domain.deadlines.domiciliation_cutoff import resolve_payment_cutoff
from ...domain.deadlines.effective_close import EffectiveFilingDeadline, effective_filing_deadline
from ...domain.deadlines.engine import DeadlineEngine, ScheduleProducer
from ...domain.deadlines.errors import NoDeadlineWindowsError
from ...domain.deadlines.festivos import DeadlineHolidayCoverage
from ...domain.deadlines.models import (
    ModeloDeadline,
    ObligationStatus,
    Schedule,
    TaxpayerProfile,
)
from ...domain.deadlines.plazo import resolve_filing_window
from ...domain.deadlines.recargo import build_recovery_for_overdue
from ...domain.modelos.work_unit import WorkUnit, WorkUnitState
from .calendar_evidence import (
    calendar_entry_filing_evidence,
    calendar_events_with_filing_evidence,
)
from .calendar_models import (
    CalendarCompleteness,
    OverviewCalendar,
    OverviewCalendarEntry,
    OverviewCalendarEntrySource,
    OverviewCalendarEvent,
    OverviewCalendarFilingEvidence,
    OverviewCalendarRange,
    OverviewCensoEnrolmentState,
    OverviewLocalFilingState,
    SuppressedCalendarEntry,
    user_state_for,
)
from .calendar_warnings import (
    build_completeness_and_warnings,
    calendar_aeat_evidence_conflict_warnings,
    calendar_applicability_disagreement_warnings,
    calendar_censo_enrolment_state,
    calendar_censo_reconciliation_warnings,
    calendar_regime_incompatibility_warnings,
    calendar_unverified_justificante_warnings,
)
from .coverage import build_obligation_coverage
from .next_actions import declare_next_action

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.deadlines.filing_window_projection import FilingWindowResolution
    from .applicability_evidence import FilingYearApplicabilityEvidence


_log = get_logger(__name__)


def _window_intersects_range(
    opens_on: date,
    nominal_closes_on: date,
    *,
    modelo: str,
    calendar_range: OverviewCalendarRange,
    operation: PinnedAuthorityOperation,
) -> bool:
    """Return whether [opens_on, effective close date] intersects the range.

    A nominal close date just before the range can move into it when it falls
    on a non-business day, so the row is placed by the effective date its
    entry will display. The effective date never precedes the nominal one, so
    it is only resolved when the nominal date alone would exclude the row.
    """
    if opens_on > calendar_range.to_date:
        return False
    if nominal_closes_on >= calendar_range.from_date:
        return True
    deadline = effective_filing_deadline(
        nominal_closes_on,
        modelo=modelo,
        operation=operation,
    )
    return deadline.closes_on >= calendar_range.from_date


def entry_intersects_range(
    obligation: ModeloDeadline,
    calendar_range: OverviewCalendarRange,
    *,
    operation: PinnedAuthorityOperation,
) -> bool:
    """Return whether ``obligation``'s filing window, to its effective close date, intersects the range.

    A window whose close is unknown keeps its nominal close as its effective
    one, the only close known for it.
    """
    del operation
    return obligation.opens_on <= calendar_range.to_date and obligation.adjusted_closes_on >= calendar_range.from_date


def _calendar_entry_key(entry: OverviewCalendarEntry) -> tuple[str, int, str]:
    return (
        entry.modelo,
        entry.filing_year or entry.period.filing_year,
        entry.period.registry_token,
    )


def _work_unit_key(unit: WorkUnit) -> tuple[str, int, str]:
    return (str(unit.modelo), unit.filing_year, unit.period.registry_token)


def registry_window_for_work_unit(
    unit: WorkUnit,
    *,
    operation: PinnedAuthorityOperation | None = None,
) -> FilingWindowResolution | None:
    """Return the deadline window resolution for ``unit`` when one is authored or projected.

    Window matching belongs to the deadline domain, which owns the year/token
    rule, authored-over-projected precedence and the no-window behaviour.
    Overview is a projection: it consumes the same resolution the
    extemporaneidad surface consumes, reads the ``opens_on`` field that surface
    does not need, and takes the payment cutoff from the deadline domain's
    cutoff resolver.
    """
    return resolve_filing_window(
        str(unit.modelo),
        unit.filing_year,
        unit.period,
        authority=operation,
    )


def _work_unit_window_span(unit: WorkUnit, resolution: FilingWindowResolution | None) -> tuple[date, date]:
    """Return the calendar span used to place a local work unit row."""
    if resolution is not None:
        return resolution.opens_on, resolution.closes_on
    if unit.period.has_date_span():
        return unit.period.start_date, unit.period.end_date
    anchor = unit.created_at.date()
    return anchor, anchor


def _work_unit_intersects_range(
    unit: WorkUnit,
    calendar_range: OverviewCalendarRange,
    *,
    operation: PinnedAuthorityOperation,
) -> bool:
    resolution = registry_window_for_work_unit(unit, operation=operation)
    opens_on, closes_on = _work_unit_window_span(unit, resolution)
    return _window_intersects_range(
        opens_on,
        closes_on,
        modelo=str(unit.modelo),
        calendar_range=calendar_range,
        operation=operation,
    )


def _work_unit_has_filing_pointers(unit: WorkUnit) -> bool:
    return unit.filed_calculation_revision_id is not None or unit.current_filing_record_id is not None


def _filing_evidence_has_local_state(
    unit: WorkUnit,
    filing_evidence: tuple[OverviewCalendarFilingEvidence, ...],
) -> bool:
    key = _work_unit_key(unit)
    for evidence in filing_evidence:
        if evidence.modelo is None or evidence.filing_year is None or evidence.period is None:
            continue
        evidence_key = (evidence.modelo, evidence.filing_year, evidence.period.registry_token)
        if evidence_key == key and evidence.local_filing_state is not OverviewLocalFilingState.NOT_READY_TO_FILE:
            return True
    return False


def local_work_unit_status(
    unit: WorkUnit,
    deadline: EffectiveFilingDeadline,
    today: date,
    due_soon_days: int,
) -> ObligationStatus:
    """Classify a local work unit, applying overview's filing gate first.

    The filing-pointer gate is overview's own concern and is the only
    intentional difference from the deadline engine's classification: a unit
    the operator has already filed locally is FILED regardless of dates. Every
    date boundary past that gate is the canonical deadline posture, read from
    :meth:`~cadrumo.domain.deadlines.effective_close.EffectiveFilingDeadline.posture_on`
    rather than restated, so a close whose holiday calendar is unpublished is
    ``UNKNOWN`` here exactly as in the schedule.
    """
    if _work_unit_has_filing_pointers(unit):
        return ObligationStatus.FILED
    return deadline.posture_on(today, due_soon_days=due_soon_days).status


def _filing_evidence_with_work_unit_pointers(
    unit: WorkUnit,
    filing_evidence: tuple[OverviewCalendarFilingEvidence, ...],
) -> tuple[OverviewCalendarFilingEvidence, ...]:
    if not _work_unit_has_filing_pointers(unit):
        return filing_evidence
    if _filing_evidence_has_local_state(unit, filing_evidence):
        return filing_evidence
    pointer_evidence = OverviewCalendarFilingEvidence(
        modelo=str(unit.modelo),
        filing_year=unit.filing_year,
        period=unit.period,
        local_filing_state=OverviewLocalFilingState.READY_TO_FILE,
        local_filing_record_id=unit.current_filing_record_id,
        local_calculation_revision_id=unit.filed_calculation_revision_id,
        evidence_source="work_unit_filing_pointers",
    )
    return (*filing_evidence, pointer_evidence)


def _annotate_entry_with_work_unit(
    entry: OverviewCalendarEntry,
    unit: WorkUnit,
) -> OverviewCalendarEntry:
    """Attach a local work unit to the registry row of its declaration.

    The row's status is the deadline engine's posture for the same close and
    reference date; only overview's filing gate can replace it, with FILED.
    """
    filed = _work_unit_has_filing_pointers(unit) or entry.filing_evidence.aeat_filed
    status = ObligationStatus.FILED if filed else entry.status
    effective_filing_evidence = _filing_evidence_with_work_unit_pointers(unit, (entry.filing_evidence,))
    return entry.model_copy(
        update={
            "status": status,
            "user_state": user_state_for(status),
            "days_overdue": entry.days_overdue if status is ObligationStatus.OVERDUE else None,
            "filing_evidence": effective_filing_evidence[-1],
            "local_work_unit_id": unit.work_unit_id,
            "local_work_unit_name": unit.name,
            "local_work_unit_revision_id": unit.revision_id,
            "recovery": None if status is ObligationStatus.FILED else entry.recovery,
            "recovery_action": None if status is ObligationStatus.FILED else entry.recovery_action,
        },
    )


def _calendar_entry_from_work_unit(
    unit: WorkUnit,
    *,
    today: date,
    due_soon_days: int,
    filing_evidence: tuple[OverviewCalendarFilingEvidence, ...],
    live_censo_verified_profile_keys: tuple[str, ...] | None,
    operation: PinnedAuthorityOperation,
) -> OverviewCalendarEntry:
    resolution = registry_window_for_work_unit(unit, operation=operation)
    opens_on, closes_on = _work_unit_window_span(unit, resolution)
    effective = effective_filing_deadline(closes_on, modelo=str(unit.modelo), operation=operation)
    # An unknown close judges nothing past its nominal date, a payment cutoff included.
    payment_cutoff_on = (
        resolve_payment_cutoff(str(unit.modelo), resolution.window, operation=operation).cutoff_on
        if resolution is not None and effective.close_known
        else None
    )
    effective_filing_evidence = _filing_evidence_with_work_unit_pointers(unit, filing_evidence)
    work_unit_fields = {
        "source": OverviewCalendarEntrySource.LOCAL_WORK_UNIT,
        "local_work_unit_id": unit.work_unit_id,
        "local_work_unit_name": unit.name,
        "local_work_unit_revision_id": unit.revision_id,
    }
    obligation = ModeloDeadline(
        modelo=Modelo(str(unit.modelo)),
        period=unit.period,
        opens_on=opens_on,
        closes_on=closes_on,
        adjusted_closes_on=effective.closes_on,
        holiday_coverage=effective.holiday_coverage,
        shift_reason=effective.shift_reason,
        shift_jurisdictions=effective.jurisdictions,
        shift_holiday_refs=effective.holiday_refs,
        payment_cutoff_on=payment_cutoff_on,
        # Overview's filing-pointer gate runs first; every date boundary past it
        # is judged against the close the filer actually has.
        status=local_work_unit_status(unit, effective, today, due_soon_days),
        boe_references=(),
        recovery=None,
    )
    return calendar_entry_from_obligation(
        obligation,
        filing_evidence=effective_filing_evidence,
        live_censo_verified_profile_keys=live_censo_verified_profile_keys,
        today=today,
        due_soon_days=due_soon_days,
        operation=operation,
    ).model_copy(update=work_unit_fields)


def _first_unit_per_address(work_units: tuple[WorkUnit, ...]) -> tuple[WorkUnit, ...]:
    """Keep one unit per natural address, so a duplicated address names one dated entry."""
    first: dict[tuple[str, int, str], WorkUnit] = {}
    for unit in sorted(work_units, key=lambda item: item.work_unit_id):
        first.setdefault(_work_unit_key(unit), unit)
    return tuple(first.values())


def local_work_unit_entries(
    work_units: tuple[WorkUnit, ...],
    *,
    calendar_range: OverviewCalendarRange,
    today: date,
    operation: PinnedAuthorityOperation,
    engine: ScheduleProducer | None = None,
    filing_evidence: tuple[OverviewCalendarFilingEvidence, ...] = (),
    live_censo_verified_profile_keys: tuple[str, ...] | None = None,
) -> tuple[OverviewCalendarEntry, ...]:
    """Date each local declaration from its own registry window, with no obligation schedule.

    Used where the taxpayer model is undeclared or its projection was refused:
    the generic schedule is unknown, yet a declaration the profile holds still
    has a registry window and a deadline. One entry names each natural address.
    """
    due_soon_days = (engine if engine is not None else DeadlineEngine(authority=operation)).due_soon_days
    return _merge_work_units_into_entries(
        (),
        work_units=_first_unit_per_address(work_units),
        calendar_range=calendar_range,
        today=today,
        due_soon_days=due_soon_days,
        filing_evidence=filing_evidence,
        live_censo_verified_profile_keys=live_censo_verified_profile_keys,
        operation=operation,
    )


def _merge_work_units_into_entries(
    entries: tuple[OverviewCalendarEntry, ...],
    *,
    work_units: tuple[WorkUnit, ...],
    calendar_range: OverviewCalendarRange,
    today: date,
    due_soon_days: int,
    filing_evidence: tuple[OverviewCalendarFilingEvidence, ...],
    live_censo_verified_profile_keys: tuple[str, ...] | None,
    operation: PinnedAuthorityOperation,
) -> tuple[OverviewCalendarEntry, ...]:
    merged = list(entries)
    registry_index = {_calendar_entry_key(entry): index for index, entry in enumerate(entries)}
    annotated_registry_keys: set[tuple[str, int, str]] = set()
    for unit in sorted(
        (item for item in work_units if item.state is not WorkUnitState.DESCARTADO),
        key=lambda item: (str(item.modelo), item.filing_year, item.period.registry_token, item.work_unit_id),
    ):
        key = _work_unit_key(unit)
        existing_index = registry_index.get(key)
        if existing_index is not None and key not in annotated_registry_keys:
            merged[existing_index] = _annotate_entry_with_work_unit(merged[existing_index], unit)
            annotated_registry_keys.add(key)
            continue
        if not _work_unit_intersects_range(
            unit,
            calendar_range,
            operation=operation,
        ):
            continue
        merged.append(
            _calendar_entry_from_work_unit(
                unit,
                today=today,
                due_soon_days=due_soon_days,
                filing_evidence=filing_evidence,
                live_censo_verified_profile_keys=live_censo_verified_profile_keys,
                operation=operation,
            ),
        )
    return tuple(
        sorted(
            merged,
            key=lambda entry: (
                entry.closes_on,
                entry.modelo,
                entry.period.filing_year,
                entry.period.registry_token,
                entry.local_work_unit_id or "",
            ),
        ),
    )


def _shift_reason_part_statement(part: str) -> str:
    """Return the localized label for one shift-reason token; holiday names pass through."""
    if part == "business_day":
        return tr("application.overview.calendar.shift.business_day")
    if part == "calendar_unavailable":
        return tr("application.overview.calendar.shift.calendar_unavailable")
    if part == "domingo":
        return tr("application.overview.calendar.shift.domingo")
    if part == "modelo_exception":
        return tr("application.overview.calendar.shift.modelo_exception")
    if part == "sabado":
        return tr("application.overview.calendar.shift.sabado")
    return part


def shift_reason_statement(shift_reason: str) -> str:
    """Return the localized statement of why a close date moved, or why it did not."""
    return " + ".join(_shift_reason_part_statement(part) for part in shift_reason.split(" + "))


def holiday_coverage_statement(coverage: DeadlineHolidayCoverage, language: OutputLanguage | None = None) -> str:
    """Return the localized statement of which holidays an effective close date accounts for.

    Every frontend renders this one statement, so none can describe an
    unverified date as final. ``language`` renders it, the configured output
    language when not given.
    """
    locale = None if language is None else language.value
    if coverage is DeadlineHolidayCoverage.NATIONAL_ONLY:
        return tr("application.overview.calendar.holiday_coverage.national_only", locale=locale)
    if coverage is DeadlineHolidayCoverage.NOT_SHIFTED:
        return tr("application.overview.calendar.holiday_coverage.not_shifted", locale=locale)
    return tr("application.overview.calendar.holiday_coverage.calendar_unavailable", locale=locale)


def _censo_enrolment_state_for(
    modelo: str,
    *,
    live_censo_verified_profile_keys: tuple[str, ...] | None,
    operation: PinnedAuthorityOperation,
    censo_enrolment_states: dict[str, OverviewCensoEnrolmentState] | None,
) -> OverviewCensoEnrolmentState:
    """Resolve a modelo's censo enrolment state once per calendar build."""
    censo_enrolment_state = None if censo_enrolment_states is None else censo_enrolment_states.get(modelo)
    if censo_enrolment_state is None:
        censo_enrolment_state = calendar_censo_enrolment_state(
            modelo=modelo,
            live_censo_verified_profile_keys=live_censo_verified_profile_keys,
            operation=operation,
        )
        if censo_enrolment_states is not None:
            censo_enrolment_states[modelo] = censo_enrolment_state
    return censo_enrolment_state


def calendar_entry_from_obligation(
    obligation: ModeloDeadline,
    *,
    filing_evidence: tuple[OverviewCalendarFilingEvidence, ...],
    live_censo_verified_profile_keys: tuple[str, ...] | None,
    today: date,
    due_soon_days: int,
    operation: PinnedAuthorityOperation,
    censo_enrolment_states: dict[str, OverviewCensoEnrolmentState] | None = None,
) -> OverviewCalendarEntry:
    """Build an overview calendar entry from a modelo obligation and its filing evidence."""
    # The obligation already carries the effective close and the status its
    # producer read from the canonical posture, on this same reference date.
    # Overview's filing-evidence gate below is its own concern and stays here.
    adjusted = obligation.adjusted_closes_on
    holiday_coverage = obligation.holiday_coverage
    period = obligation.period
    status = obligation.status
    evidence = calendar_entry_filing_evidence(
        modelo=obligation.modelo,
        filing_year=period.filing_year,
        period=period,
        evidence=filing_evidence,
    )
    if evidence.aeat_filed:
        status = ObligationStatus.FILED
    recovery = None
    if status is ObligationStatus.OVERDUE:
        try:
            recovery = build_recovery_for_overdue(
                closes_on=adjusted,
                reference_today=today,
                modelo=str(obligation.modelo),
                period=period,
                operation=operation,
            )
        except (FileNotFoundError, ValueError) as exc:
            _log.debug(
                "overview calendar has no recovery registry entry",
                extra={
                    "modelo": str(obligation.modelo),
                    "period": str(period),
                    "error_type": type(exc).__name__,
                },
            )
    censo_enrolment_state = _censo_enrolment_state_for(
        obligation.modelo,
        live_censo_verified_profile_keys=live_censo_verified_profile_keys,
        operation=operation,
        censo_enrolment_states=censo_enrolment_states,
    )
    return OverviewCalendarEntry(
        modelo=obligation.modelo,
        period=period,
        opens_on=obligation.opens_on,
        closes_on=obligation.closes_on,
        adjusted_closes_on=adjusted,
        shift_reason=obligation.shift_reason,
        holiday_refs=obligation.shift_holiday_refs,
        jurisdictions=obligation.shift_jurisdictions,
        holiday_coverage=holiday_coverage,
        payment_cutoff_on=obligation.payment_cutoff_on,
        evaluated_on=today,
        days_overdue=(today - adjusted).days if status is ObligationStatus.OVERDUE else None,
        status=status,
        user_state=user_state_for(status),
        recovery=recovery,
        recovery_action=(
            declare_next_action(
                "operator.modelo.work.create",
                modelo=str(obligation.modelo),
                year=period.filing_year,
                period=period.registry_token,
            )
            if recovery is not None
            else None
        ),
        filing_year=period.filing_year,
        censo_enrolment_state=censo_enrolment_state,
        filing_evidence=evidence,
    )


def _schedules_for_calendar_range(
    profile: TaxpayerProfile,
    calendar_range: OverviewCalendarRange,
    *,
    today: date,
    engine: ScheduleProducer | None,
    operation: PinnedAuthorityOperation,
) -> tuple[ScheduleProducer, list[Schedule]]:
    """Return the deadline engine and per-year schedules covering ``calendar_range``.

    A year inside the range with no registered deadline windows is a normal
    "no data yet" state (registry-track gap R1), not an error: the year
    contributes zero entries and every other covered year still resolves.
    This catch is deliberately the narrow ``_NoDeadlineWindowsError``
    subtype; a genuine registry-integrity fault (validation failure,
    profile-condition evaluation failure) raises the bare
    ``ScheduleComputationError`` and must propagate, mirroring the graceful
    degradation ``overview explain`` applies via the same narrow catch.
    """
    deadline_engine = engine if engine is not None else DeadlineEngine(authority=operation)
    schedules: list[Schedule] = []
    # The prior year that ``covered_years`` adds for late-opening windows can
    # sit below the registry's support floor, where nothing resolves at all.
    modelo_ids = operation.modelo_ids()
    support = operation.modelo_directory(modelo_ids[0]).supported_filing_years if modelo_ids else None
    for year in calendar_range.covered_years():
        if support is not None and not support.admits_filing_year(year):
            continue
        try:
            schedules.append(deadline_engine.compute(profile, year, today=today))
        except NoDeadlineWindowsError as exc:
            _log.debug(
                "overview calendar ignored covered year with no registered deadline windows",
                extra={"year": year, "error_type": type(exc).__name__},
            )
            continue
    return deadline_engine, schedules


def _calendar_obligation_projection(
    obligation: ModeloDeadline,
    *,
    profile: TaxpayerProfile,
    calendar_range: OverviewCalendarRange,
    show_suppressed: bool,
    filing_evidence: tuple[OverviewCalendarFilingEvidence, ...],
    live_censo_verified_profile_keys: tuple[str, ...] | None,
    today: date,
    due_soon_days: int,
    operation: PinnedAuthorityOperation,
    censo_enrolment_states: dict[str, OverviewCensoEnrolmentState],
    applicability_evidence: FilingYearApplicabilityEvidence | None = None,
) -> tuple[
    OverviewCalendarEntry | None,
    SuppressedCalendarEntry | None,
    str | None,
    str | None,
]:
    """Classify one scheduled obligation for the requested calendar projection."""
    intersects_range = entry_intersects_range(
        obligation,
        calendar_range,
        operation=operation,
    )
    filing_year = obligation.period.filing_year
    applicability = derive_modelo_applicability(
        profile if applicability_evidence is None else applicability_evidence.profile_for_year(filing_year),
        obligation.modelo,
        reference_date=date(filing_year, 12, 31),
        operation=operation,
        ledger_payer_facts=(
            {} if applicability_evidence is None else applicability_evidence.ledger_payer_facts_for_year(filing_year)
        ),
    )
    disagreeing_modelo = (
        obligation.modelo if applicability.evidence_disagreement is not None and intersects_range else None
    )
    if applicability.verdict is not ApplicabilityVerdict.APPLICABLE:
        suppressed_entry = (
            SuppressedCalendarEntry(
                modelo=obligation.modelo,
                period=obligation.period,
                verdict=applicability.verdict,
                reason=applicability.reason,
            )
            if show_suppressed and intersects_range
            else None
        )
        return None, suppressed_entry, None, disagreeing_modelo

    if not intersects_range:
        return None, None, obligation.modelo, disagreeing_modelo
    entry = calendar_entry_from_obligation(
        obligation,
        filing_evidence=filing_evidence,
        live_censo_verified_profile_keys=live_censo_verified_profile_keys,
        today=today,
        due_soon_days=due_soon_days,
        operation=operation,
        censo_enrolment_states=censo_enrolment_states,
    )
    return entry, None, obligation.modelo, disagreeing_modelo


def _entries_and_suppressed_from_schedules(
    schedules: list[Schedule],
    *,
    profile: TaxpayerProfile,
    calendar_range: OverviewCalendarRange,
    show_suppressed: bool,
    filing_evidence: tuple[OverviewCalendarFilingEvidence, ...],
    live_censo_verified_profile_keys: tuple[str, ...] | None,
    today: date,
    due_soon_days: int,
    operation: PinnedAuthorityOperation,
    applicability_evidence: FilingYearApplicabilityEvidence | None = None,
) -> tuple[list[OverviewCalendarEntry], list[SuppressedCalendarEntry], set[str], set[str]]:
    """Project every schedule's obligations into applicable calendar entries.

    Each modelo's applicability is DERIVED from the taxpayer model. Only a
    positively ``APPLICABLE`` verdict earns a calendar row. An obligation the
    taxpayer model excludes (``NOT_APPLICABLE`` -- e.g. Modelo 130 for a pure
    landlord) is dropped; so is a cuota self-assessment routed to the
    attribution pass-through (``ATTRIBUTION_PASS_THROUGH`` -- a comunidad de
    bienes owes no IS / IRPF cuota of its own); so is a modelo the seed table
    cannot yet decide (``INCOMPLETE`` -- no seed rule). Surfacing any of
    these as a confident due row would diverge from ``explain`` and
    re-create the confident-wrong-obligation defect. The seed covers the
    core persona set; full per-modelo coverage is a deferred expansion (see
    ``_SEED_COVERAGE_NOTICE``).

    With ``applicability_evidence``, each obligation is decided on the profile
    as of its own filing year and on the ledger derivations for that year. The
    fourth result names the modelos whose in-range rows carry a disagreement
    between the profile answer and the ledger.
    """
    entries: list[OverviewCalendarEntry] = []
    suppressed: list[SuppressedCalendarEntry] = []
    coverage_surface_modelos: set[str] = set()
    disagreeing_modelos: set[str] = set()
    # Every row shares this pinned authority and live-censo tuple. Resolve
    # enrolment once per modelo, rather than reloading rules for each period.
    censo_enrolment_states: dict[str, OverviewCensoEnrolmentState] = {}
    for obligation in (row for schedule in schedules for row in schedule.obligations):
        entry, suppressed_entry, covered_modelo, disagreeing_modelo = _calendar_obligation_projection(
            obligation,
            profile=profile,
            calendar_range=calendar_range,
            show_suppressed=show_suppressed,
            filing_evidence=filing_evidence,
            live_censo_verified_profile_keys=live_censo_verified_profile_keys,
            today=today,
            due_soon_days=due_soon_days,
            operation=operation,
            censo_enrolment_states=censo_enrolment_states,
            applicability_evidence=applicability_evidence,
        )
        if entry is not None:
            entries.append(entry)
        if suppressed_entry is not None:
            suppressed.append(suppressed_entry)
        if covered_modelo is not None:
            coverage_surface_modelos.add(covered_modelo)
        if disagreeing_modelo is not None:
            disagreeing_modelos.add(disagreeing_modelo)
    return entries, suppressed, coverage_surface_modelos, disagreeing_modelos


def _undeclared_taxpayer_model_reason(profile: TaxpayerProfile) -> str:
    """Name the profile fact whose absence leaves the taxpayer model undeclared."""
    if profile.entity_type is None:
        return tr("application.overview.calendar.taxpayer_model_undeclared.entity_type")
    return tr("application.overview.calendar.taxpayer_model_undeclared.irpf_income_categories")


def build_overview_calendar(
    profile: TaxpayerProfile,
    calendar_range: OverviewCalendarRange,
    *,
    operation: PinnedAuthorityOperation,
    today: date,
    engine: ScheduleProducer | None = None,
    raw_values: Mapping[str, object] | None = None,
    show_suppressed: bool = False,
    events: tuple[OverviewCalendarEvent, ...] = (),
    filing_evidence: tuple[OverviewCalendarFilingEvidence, ...] = (),
    work_units: tuple[WorkUnit, ...] = (),
    live_censo_verified_profile_keys: tuple[str, ...] | None = None,
    applicability_evidence: FilingYearApplicabilityEvidence | None = None,
) -> OverviewCalendar:
    """Build a calendar over the inclusive range from already-loaded evidence.

    The caller supplies a generation-pinned authority operation and a reference
    date. An optional engine and raw values drive obligation scheduling; events,
    filing evidence, and work units are merged without storage or network I/O.
    Suppressed obligations are included only when ``show_suppressed`` is true.
    Live censo keys and per-filing-year applicability evidence inform warnings
    and applicability decisions. Years without registered deadline windows
    contribute no entries. An undeclared taxpayer model yields an incomplete
    calendar with obligation coverage rather than guessed obligations.

    ``profile`` is a :class:`TaxpayerProfile`.
    """
    if not taxpayer_model_is_declared(profile):
        # An undeclared taxpayer model yields an explicit
        # incomplete answer — never a confident wrong obligation. The
        # engine does not fall back to the autónomo guess. The profile's own
        # local declarations are not guesses: each keeps its dated entry from
        # its registry window, so the operator still sees when it is due.
        # Coverage is reconciled with those declarations surfaced and nothing
        # else, so the report honestly shows the rest of the obligation universe
        # as advised/undetermined rather than empty — an undeclared profile can
        # under-scope the most, so it must not read as "nothing to file".
        work_entries = local_work_unit_entries(
            work_units,
            calendar_range=calendar_range,
            today=today,
            operation=operation,
            engine=engine,
            filing_evidence=filing_evidence,
            live_censo_verified_profile_keys=live_censo_verified_profile_keys,
        )
        return OverviewCalendar(
            range=calendar_range,
            evaluated_on=today,
            entries=work_entries,
            generated_at=now(),
            warnings=(),
            completeness=CalendarCompleteness(),
            taxpayer_model_declared=False,
            incomplete_reason=_undeclared_taxpayer_model_reason(profile),
            events=calendar_events_with_filing_evidence(events, filing_evidence),
            coverage=build_obligation_coverage(
                profile,
                {str(unit.modelo) for unit in work_units if unit.state is not WorkUnitState.DESCARTADO},
                today=today,
                operation=operation,
            ),
        )

    deadline_engine, schedules = _schedules_for_calendar_range(
        profile,
        calendar_range,
        today=today,
        engine=engine,
        operation=operation,
    )
    due_soon_days = deadline_engine.due_soon_days
    entries, suppressed, coverage_surface_modelos, disagreeing_modelos = _entries_and_suppressed_from_schedules(
        schedules,
        profile=profile,
        calendar_range=calendar_range,
        show_suppressed=show_suppressed,
        filing_evidence=filing_evidence,
        live_censo_verified_profile_keys=live_censo_verified_profile_keys,
        today=today,
        due_soon_days=due_soon_days,
        operation=operation,
        applicability_evidence=applicability_evidence,
    )
    entries.sort(
        key=lambda entry: (
            entry.closes_on,
            entry.modelo,
            entry.period.filing_year,
            entry.period.registry_token,
        ),
    )
    suppressed.sort(key=lambda s: (s.modelo, s.period.filing_year, s.period.registry_token))
    entries_tuple = _merge_work_units_into_entries(
        tuple(entries),
        work_units=work_units,
        calendar_range=calendar_range,
        today=today,
        due_soon_days=due_soon_days,
        filing_evidence=filing_evidence,
        live_censo_verified_profile_keys=live_censo_verified_profile_keys,
        operation=operation,
    )
    completeness, warnings = build_completeness_and_warnings(raw_values, entries_tuple, operation=operation)
    censo_warnings = calendar_censo_reconciliation_warnings(
        entries=entries_tuple,
        live_censo_verified_profile_keys=live_censo_verified_profile_keys,
    )
    enriched_events = calendar_events_with_filing_evidence(events, filing_evidence)
    justificante_warnings = calendar_unverified_justificante_warnings(
        entries=entries_tuple,
        events=enriched_events,
    )
    evidence_conflict_warnings = calendar_aeat_evidence_conflict_warnings(entries=entries_tuple)
    regime_incompatibility_warnings = calendar_regime_incompatibility_warnings(
        iva_regime=profile.iva_regime,
        entries=entries_tuple,
        operation=operation,
    )
    coverage = build_obligation_coverage(
        profile,
        coverage_surface_modelos | {entry.modelo for entry in entries_tuple},
        today=today,
        operation=operation,
    )
    return OverviewCalendar(
        range=calendar_range,
        evaluated_on=today,
        entries=entries_tuple,
        generated_at=now(),
        warnings=(
            warnings
            + censo_warnings
            + justificante_warnings
            + evidence_conflict_warnings
            + regime_incompatibility_warnings
            + calendar_applicability_disagreement_warnings(disagreeing_modelos)
        ),
        completeness=completeness,
        suppressed_entries=tuple(suppressed),
        events=enriched_events,
        coverage=coverage,
    )
