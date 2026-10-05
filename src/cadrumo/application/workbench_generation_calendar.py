"""Pure assembly of one installed-workbench projection generation.

The installed-session composition root owns secure readers and source
projectors.  It supplies the already-loaded, frontend-neutral inputs declared
here; this module joins those inputs into one immutable generation and derives
the Home and search projections through their existing application composers.

An absent reader result is deliberately not represented by an empty tuple or
an empty projection.  ``LOCKED``, ``NEVER_CAPTURED`` and ``UNAVAILABLE`` are
separate source outcomes and carry an explicit refusal.  The output contract
does not retain the source-input models, so raw source facts cannot cross this
assembly boundary accidentally.

Core types:
:class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`,
:class:`~cadrumo.domain.invoices.models.InvoiceCatalogue`,
:class:`~cadrumo.domain.modelos.filing_record.ModeloRecord`,
:class:`~cadrumo.domain.deadlines.models.TaxpayerProfile`,
:class:`~cadrumo.domain.transactions.models.TransactionCatalogue`,
:class:`~cadrumo.domain.user_profile.values.UserProfileRecord`.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import date
from typing import TYPE_CHECKING, Final, Protocol, runtime_checkable

from ..core.errors.hierarchy import InternalInvariantError
from ..core.time.utc import UtcInstant
from ..domain.deadlines.errors import ProfileError
from ..domain.deadlines.models import TaxpayerProfile
from ..domain.modelos.filing_record import ModeloRecord, ModeloRecordCatalogue
from ..domain.modelos.work_unit import WorkUnitCatalogue
from ..domain.user_profile.errors import UserProfileValidationError
from ..domain.user_profile.values import UserProfileRecord
from .invoices.source_resolver_ports import InvoiceSourceResolverPorts
from .modelo.declarations_calendar import (
    DeclarationsCalendarProjectionV1,
    DeclarationsCalendarSource,
    DeclarationsCalendarSourceObservationV1,
    project_declarations_calendar,
)
from .modelo.declarations_workspace_contracts import (
    DeclarationsWorkspaceAvailability,
    DeclarationsWorkspaceZone,
    DeclarationsWorkspaceZoneObservationV1,
)
from .overview.agenda import OverviewAgenda, build_overview_agenda
from .overview.applicability_evidence import FilingYearApplicabilityEvidence, bind_filing_year_applicability_evidence
from .overview.calendar import build_overview_calendar
from .overview.calendar_models import OverviewCalendar, OverviewCalendarRange
from .overview.evidence import (
    AeatCalendarEvidenceSources,
    CalendarEvidenceProjection,
    CalendarEvidenceReadOutcome,
    LocalCalendarEvidenceSources,
    build_calendar_evidence_projection,
)
from .overview.home import (
    HomeAvailability,
    HomeZoneState,
)
from .user_profile.projections import projection_for_taxpayer
from .workbench_capture_memory import WorkbenchCalendarMemoKey, WorkbenchCalendarWork, WorkbenchCaptureMemory

if TYPE_CHECKING:
    from ..domain.calculations.registry.authority import PinnedAuthorityOperation


def declared_tax_id(raw_values: Mapping[str, object]) -> str | None:
    """Return the profile's own NIF, never the schema's placeholder default."""
    declared = raw_values.get("identity.tax_id")
    if not isinstance(declared, str) or not declared.strip():
        return None
    return declared.strip()


def declarations_observation(
    zone: DeclarationsWorkspaceZone,
    observed_at: UtcInstant,
) -> DeclarationsWorkspaceZoneObservationV1:
    """Wrap the measured declarations zone with its observation time."""
    return DeclarationsWorkspaceZoneObservationV1(
        zone=zone,
        availability=DeclarationsWorkspaceAvailability.AVAILABLE,
        observed_at=observed_at,
    )


def _scope_filing_records(
    filing_records: tuple[ModeloRecord, ...],
    schedule_calendar: OverviewCalendar,
) -> tuple[ModeloRecord, ...]:
    """Keep only evidence addressed by this legal-calendar query.

    The local source remains observed and available even when none of its
    profile-wide filing records belongs to the requested window. That is a
    measured empty query result, not an invented empty authority.
    """
    addresses = {
        (entry.modelo, entry.period.filing_year, entry.period.registry_token) for entry in schedule_calendar.entries
    }
    return tuple(
        record
        for record in filing_records
        if (str(record.modelo), record.filing_year, record.period.registry_token) in addresses
    )


def _schedule_observation(
    calendar: OverviewCalendar,
    observed_at: UtcInstant,
) -> DeclarationsCalendarSourceObservationV1:
    if not calendar.taxpayer_model_declared:
        return DeclarationsCalendarSourceObservationV1(
            source=DeclarationsCalendarSource.SCHEDULE,
            availability=HomeAvailability.UNAVAILABLE,
            reason_code=_TAXPAYER_MODEL_UNDECLARED,
        )
    return DeclarationsCalendarSourceObservationV1(
        source=DeclarationsCalendarSource.SCHEDULE,
        availability=HomeAvailability.AVAILABLE,
        observed_at=observed_at,
    )


_TAXPAYER_PROFILE_INCOMPLETE: Final = "workbench.home.taxpayer_profile_incomplete"


_TAXPAYER_MODEL_UNDECLARED: Final = "workbench.calendar.taxpayer_model_undeclared"


@dataclass(frozen=True, slots=True)
class WorkbenchCalendarInputs:
    """The calendar-derived Home and Declarations inputs, or why there are none.

    ``refusal`` is set exactly when the calendar could not be built at all;
    ``agenda_refusal`` is set whenever the agenda cannot be offered, which also
    covers a calendar that was built but has no taxpayer model to schedule.
    """

    agenda_evidence_state: HomeZoneState
    declarations_calendar: DeclarationsCalendarProjectionV1
    agenda: OverviewAgenda | None
    agenda_refusal: HomeZoneState | None
    refusal: HomeZoneState | None


def _taxpayer_profile_refusal(
    raw_values: Mapping[str, str],
    *,
    operation: PinnedAuthorityOperation,
) -> HomeZoneState:
    """Name the profile paths the operator still owes, as one Home zone state.

    The paths come from the profile completeness contract, which the manager
    reads too, so the zone points the operator at exactly the fields the
    Profile destination lists as required.
    """
    from .user_profile.completeness import conditional_profile_missing_required, missing_required_field_paths

    missing = (
        *missing_required_field_paths(operation.profile_schema(), raw_values),
        *conditional_profile_missing_required(raw_values),
    )
    return HomeZoneState(
        availability=HomeAvailability.UNAVAILABLE,
        reason_code=_TAXPAYER_PROFILE_INCOMPLETE,
        missing_profile_paths=tuple(dict.fromkeys(missing)),
    )


@runtime_checkable
class RevisionedCatalogueStore(Protocol):
    """A store that can state a revision of its whole catalogue without decrypting it.

    The revision changes with every committed write; ``None`` means the store
    cannot state one right now.
    """

    def load_revision(self) -> str | None:
        """Return the current catalogue revision, or ``None`` when it cannot be stated."""
        ...


@dataclass(frozen=True, slots=True)
class CalendarMemo:
    """Where one capture may reuse its calendar work, and under which input identity."""

    memory: WorkbenchCaptureMemory | None
    key: WorkbenchCalendarMemoKey

    def reuse(self, build: Callable[[], WorkbenchCalendarWork]) -> WorkbenchCalendarWork:
        """Reuse this generation calendar work when capture memory is available."""
        return build() if self.memory is None else self.memory.calendar.reuse(self.key, build)


def read_workbench_calendar_inputs(
    *,
    record: UserProfileRecord,
    raw_values: Mapping[str, str],
    as_of: date,
    work_units: WorkUnitCatalogue,
    filings: ModeloRecordCatalogue,
    observed_at: UtcInstant,
    operation: PinnedAuthorityOperation,
    memo: CalendarMemo,
    invoice_source_ports: InvoiceSourceResolverPorts,
    aeat_evidence: CalendarEvidenceReadOutcome[AeatCalendarEvidenceSources] | None = None,
) -> WorkbenchCalendarInputs:
    """Project the taxpayer once and build every calendar-derived input from it.

    A profile the taxpayer projection refuses is an incomplete profile, not a
    broken session: the operator reached it by editing a field. The refusal is
    published on the zones that need the projection, and every other zone of
    the generation is served, rather than the whole workbench failing to start.

    Each obligation is decided on the per-filing-year evidence the overview
    reads bind: the profile as of the year and the ledger's own derivations
    from ``invoice_source_ports``, so the workbench and the CLI reach the same
    verdict for the same records.

    Parameter types: ``record`` (:class:`~cadrumo.domain.user_profile.values.UserProfileRecord`).
    """
    try:
        taxpayer = projection_for_taxpayer(
            record,
            tax_id_default="00000000T",
            schema=operation.profile_schema(),
        )
    except (ProfileError, UserProfileValidationError):
        refusal = _taxpayer_profile_refusal(raw_values, operation=operation)
        return WorkbenchCalendarInputs(
            agenda_evidence_state=refusal,
            declarations_calendar=_refused_declarations_calendar(refusal, as_of=as_of, observed_at=observed_at),
            agenda=None,
            agenda_refusal=refusal,
            refusal=refusal,
        )
    evidence, declarations_calendar, agenda, model_declared = _build_workbench_calendar_inputs(
        taxpayer=taxpayer,
        raw_values=raw_values,
        as_of=as_of,
        work_units=work_units,
        filings=filings,
        observed_at=observed_at,
        operation=operation,
        memo=memo,
        aeat_evidence=aeat_evidence,
        applicability_evidence=bind_filing_year_applicability_evidence(
            record=record,
            schema=operation.profile_schema(),
            bucket_id=str(record.profile_id),
            invoice_source_ports=invoice_source_ports,
            operation=operation,
            today=as_of,
        ),
    )
    if not model_declared:
        # The schedule observation already says why the calendar is empty; the
        # agenda derived from the same missing model must say so too rather
        # than read as a verified absence of dates.
        return WorkbenchCalendarInputs(
            agenda_evidence_state=evidence.aeat_state,
            declarations_calendar=declarations_calendar,
            agenda=None,
            agenda_refusal=HomeZoneState(
                availability=HomeAvailability.UNAVAILABLE,
                reason_code=_TAXPAYER_MODEL_UNDECLARED,
            ),
            refusal=None,
        )
    return WorkbenchCalendarInputs(
        agenda_evidence_state=evidence.aeat_state,
        declarations_calendar=declarations_calendar,
        agenda=agenda,
        agenda_refusal=None,
        refusal=None,
    )


def _refused_declarations_calendar(
    refusal: HomeZoneState,
    *,
    as_of: date,
    observed_at: UtcInstant,
) -> DeclarationsCalendarProjectionV1:
    """Publish a Declarations calendar that states why it has no schedule.

    Declarations stays admitted when only the calendar is refused, and an
    admitted Declarations destination always carries a calendar. The honest
    calendar here is an empty one whose every source says why it is empty.
    """
    reason_code = refusal.reason_code
    if reason_code is None:
        raise InternalInvariantError("a refused Declarations calendar requires a reason")
    unavailable = HomeZoneState(availability=HomeAvailability.UNAVAILABLE, reason_code=reason_code)
    evidence = build_calendar_evidence_projection(
        local=CalendarEvidenceReadOutcome[LocalCalendarEvidenceSources](state=unavailable),
        aeat=CalendarEvidenceReadOutcome[AeatCalendarEvidenceSources](state=unavailable),
    )
    calendar = OverviewCalendar(
        range=_calendar_query_range(as_of),
        entries=(),
        generated_at=observed_at,
        evaluated_on=as_of,
        taxpayer_model_declared=False,
    )
    return project_declarations_calendar(
        calendar=calendar,
        evidence=evidence,
        as_of=as_of,
        schedule_observation=DeclarationsCalendarSourceObservationV1(
            source=DeclarationsCalendarSource.SCHEDULE,
            availability=HomeAvailability.UNAVAILABLE,
            reason_code=reason_code,
        ),
    )


def _calendar_query_range(as_of: date) -> OverviewCalendarRange:
    """Cover the latest completed filing year and the current calendar year.

    Annual returns for the completed filing year can close in the current
    calendar year, while its quarterly returns closed in the prior one.  A
    current-year-only projection made those quarterly natural addresses
    unreachable from the TUI even though the pinned authority still supports
    them.
    """
    return OverviewCalendarRange(
        from_date=date(as_of.year - 1, 1, 1),
        to_date=date(as_of.year, 12, 31),
    )


def unbound_calendar_aeat_evidence() -> CalendarEvidenceReadOutcome[AeatCalendarEvidenceSources]:
    """Report an unavailable AEAT calendar reader without inventing evidence."""
    return CalendarEvidenceReadOutcome(
        state=HomeZoneState(
            availability=HomeAvailability.NEVER_CAPTURED,
            reason_code="workbench.calendar.aeat_reader_unavailable",
        )
    )


def _build_workbench_calendar_inputs(
    *,
    taxpayer: TaxpayerProfile,
    raw_values: Mapping[str, object],
    as_of: date,
    work_units: WorkUnitCatalogue,
    filings: ModeloRecordCatalogue,
    observed_at: UtcInstant,
    operation: PinnedAuthorityOperation,
    memo: CalendarMemo,
    aeat_evidence: CalendarEvidenceReadOutcome[AeatCalendarEvidenceSources] | None = None,
    applicability_evidence: FilingYearApplicabilityEvidence | None = None,
) -> tuple[CalendarEvidenceProjection, DeclarationsCalendarProjectionV1, OverviewAgenda, bool]:
    query_range = _calendar_query_range(as_of)

    def evidence_for(schedule_calendar: OverviewCalendar) -> CalendarEvidenceProjection:
        projection = build_calendar_evidence_projection(
            local=CalendarEvidenceReadOutcome(
                state=HomeZoneState(availability=HomeAvailability.AVAILABLE, observed_at=observed_at),
                value=LocalCalendarEvidenceSources(
                    filing_records=_scope_filing_records(
                        tuple(filings.records.values()),
                        schedule_calendar,
                    ),
                ),
            ),
            aeat=aeat_evidence or unbound_calendar_aeat_evidence(),
            expected_tax_id=taxpayer.tax_id,
        )
        addresses = {
            (row.modelo, row.period.filing_year, row.period.registry_token) for row in schedule_calendar.entries
        }
        return replace(
            projection,
            evidence=tuple(
                row
                for row in projection.evidence
                if row.period is not None and (row.modelo, row.filing_year, row.period.registry_token) in addresses
            ),
        )

    def compute() -> WorkbenchCalendarWork:
        schedule_calendar = build_overview_calendar(
            taxpayer,
            query_range,
            today=as_of,
            raw_values=raw_values,
            work_units=tuple(work_units.values()),
            operation=operation,
            applicability_evidence=applicability_evidence,
        )
        return WorkbenchCalendarWork(
            schedule_calendar=schedule_calendar,
            calendar=build_overview_calendar(
                taxpayer,
                query_range,
                today=as_of,
                raw_values=raw_values,
                filing_evidence=evidence_for(schedule_calendar).evidence,
                work_units=tuple(work_units.values()),
                operation=operation,
                applicability_evidence=applicability_evidence,
            ),
            agenda=build_overview_agenda(
                taxpayer,
                as_of=as_of,
                raw_values=raw_values,
                operation=operation,
                applicability_evidence=applicability_evidence,
            ),
        )

    work = memo.reuse(compute)
    # The evidence rows depend only on the memo key's inputs; their observation
    # state is this capture's own, so the projection is rebuilt every time.
    evidence = evidence_for(work.schedule_calendar)
    declarations_calendar = project_declarations_calendar(
        calendar=work.calendar,
        evidence=evidence,
        as_of=as_of,
        schedule_observation=_schedule_observation(work.calendar, observed_at),
    )
    return evidence, declarations_calendar, work.agenda, work.calendar.taxpayer_model_declared
