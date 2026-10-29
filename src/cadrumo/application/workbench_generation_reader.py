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
:class:`~cadrumo.domain.invoices.catalogue.InvoiceCatalogue`,
:class:`~cadrumo.domain.modelos.filing_record.ModeloRecord`,
:class:`~cadrumo.domain.deadlines.models.TaxpayerProfile`,
:class:`~cadrumo.domain.transactions.models.TransactionCatalogue`,
:class:`~cadrumo.domain.user_profile.values.UserProfileRecord`.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Final, NamedTuple
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from ..core.diagnostic_log import DiagnosticValue, diagnostic_phase, diagnostic_scope
from ..core.errors.hierarchy import InternalInvariantError
from ..core.hashing import content_hash_hex
from ..core.identifier_grammar import NamespacedId
from ..core.logging import get_logger
from ..core.time.utc import UtcInstant
from ..domain.buckets.event import (
    BucketEvent,
    BucketEventHistoryCatalogue,
    BucketEventObjectType,
    BucketEventType,
    bucket_event_order_key,
)
from ..domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ..domain.invoices.catalogue import InvoiceCatalogue
from ..domain.invoices.protocols import InvoiceCatalogueRepositoryProtocol
from ..domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
)
from ..domain.modelos.filing_record import ModeloRecord, ModeloRecordCatalogue
from ..domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
    VerificationReportCatalogueRepositoryProtocol,
)
from ..domain.modelos.verification_report import (
    VerificationReportCatalogue,
)
from ..domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue
from ..domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ..domain.transactions.models import TransactionCatalogue
from ..domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..domain.user_profile.values import UserProfileRecord
from .aeat_sync.workspace import AeatSyncWorkspaceProjectionError, AeatSyncWorkspaceProjectionV1
from .calculations.verification_report_gate import require_verification_report_coordinates_current
from .ledger.workspace import (
    LedgerWorkspaceProjectionV1,
)
from .modelo.declaration_summary import declaration_summary
from .modelo.declarations_list import DeclarationListInputs
from .modelo.declarations_portfolio import project_declarations_portfolio
from .modelo.declarations_workspace_contracts import (
    DeclarationResultCasillaReaderV1,
    DeclarationsLifecycleKind,
    DeclarationsSanitizedLifecycleFactV1,
    DeclarationsWorkspaceAvailability,
    DeclarationsWorkspaceProjectionError,
    DeclarationsWorkspaceProjectionV1,
    DeclarationsWorkspaceZone,
    DeclarationsWorkspaceZoneObservationV1,
)
from .modelo.reconciliation_records import ModeloReconciliationRecord
from .modelo.work_history_read import LIFECYCLE_KIND_BY_EVENT
from .modelo.workspace_models import (
    ModeloWorkspaceProjectionV1,
)
from .operations.registry import OperationPublicContractSetV1
from .overview.applicability_evidence import loaded_invoice_source_ports
from .overview.evidence import (
    AeatCalendarEvidenceSources,
    CalendarEvidenceProjection,
    CalendarEvidenceReadOutcome,
    LocalCalendarEvidenceSources,
    build_calendar_evidence_projection,
)
from .overview.home import (
    HomeAccountSession,
    HomeAvailability,
    HomeZoneState,
)
from .user_profile.censal_observation import CensalObservation
from .user_profile.projections import record_to_path_values
from .workbench_capture_memory import WorkbenchCalendarMemoKey, WorkbenchCaptureMemory
from .workbench_generation_calendar import (
    CalendarMemo,
    RevisionedCatalogueStore,
    WorkbenchCalendarInputs,
    declarations_observation,
    declared_tax_id,
    read_workbench_calendar_inputs,
    unbound_calendar_aeat_evidence,
)
from .workbench_generation_contracts import (
    ProfileRecordReadRepositoryV1,
    WorkbenchGenerationInputsV1,
)
from .workbench_generation_home import build_workbench_generation_inputs

_LOGGER = get_logger(__name__)
_CAPTURE_PHASE_EVENT: Final = "workbench_capture_phase"
_AEAT_SYNC_READER_UNAVAILABLE: Final[str] = "workbench.aeat_sync.reader_unavailable"
_AEAT_SYNC_SNAPSHOT_PROJECTOR_UNAVAILABLE: Final[str] = "workbench.aeat_sync.snapshot_projector_unavailable"


if TYPE_CHECKING:
    from ..domain.calculations.registry.authority import PinnedAuthorityOperation
    from .ledger.action_ports import LedgerActionPorts

_FILING_HISTORY_KINDS: Final[frozenset[DeclarationsLifecycleKind]] = frozenset(
    {
        DeclarationsLifecycleKind.CREATED,
        DeclarationsLifecycleKind.RENAMED,
        DeclarationsLifecycleKind.CALCULATED,
        DeclarationsLifecycleKind.VERIFIED,
        DeclarationsLifecycleKind.VERIFICATION_REFUSED,
        DeclarationsLifecycleKind.FILED,
        DeclarationsLifecycleKind.RECONCILED,
        DeclarationsLifecycleKind.OBSERVATION_OVERRIDDEN,
        DeclarationsLifecycleKind.OBSERVATION_OVERRIDE_CLEARED,
    }
)
_LIFECYCLE_KIND_BY_EVENT: Final[Mapping[BucketEventType, DeclarationsLifecycleKind]] = {
    event: kind for event, kind in LIFECYCLE_KIND_BY_EVENT.items() if kind in _FILING_HISTORY_KINDS
}


"""The bucket events the profile's filing history reports, by the lifecycle meaning each carries.

The meaning of every event is the declaration history's; this history reports
the meanings above, and leaves exports, corrections, discards and the events
with no lifecycle meaning to each declaration's own history.
"""


def _capture_phase(phase: str) -> AbstractContextManager[dict[str, DiagnosticValue]]:
    """Record how long one step of a capture took, and what it counted."""
    return diagnostic_phase(_LOGGER, _CAPTURE_PHASE_EVENT, phase)


def _timed[ResultT](
    phase: str, read: Callable[[], ResultT], *, count: Callable[[ResultT], int | None] | None = None
) -> ResultT:
    """Run one capture step inside its phase record, counting the items it produced when asked."""
    with _capture_phase(phase) as measured:
        result = read()
        if count is not None:
            measured["item_count"] = count(result)
        return result


def _lifecycle_work_unit_id(
    event: BucketEvent,
    *,
    revisions: CalculationRevisionCatalogue,
    verification: VerificationReportCatalogue | None,
    filings: ModeloRecordCatalogue,
) -> str | None:
    """Resolve the declaration an event belongs to.

    An event about an observation has no declaration object of its own, so it
    names its work unit in the payload; every other event resolves through the
    object it references.
    """
    payload_work_unit_id = event.payload.get("work_unit_id")
    if payload_work_unit_id is not None and payload_work_unit_id:
        return payload_work_unit_id
    object_id = event.object_id
    if event.object_type is BucketEventObjectType.WORK_UNIT:
        return object_id
    if event.object_type is BucketEventObjectType.CALCULATION_REVISION:
        return _revision_event_work_unit_id(object_id, revisions)
    if event.object_type is BucketEventObjectType.VERIFICATION_REPORT:
        return _verification_event_work_unit_id(object_id, revisions, verification)
    if event.object_type is BucketEventObjectType.FILING_RECORD:
        return _filing_event_work_unit_id(object_id, filings)
    return None


def _revision_event_work_unit_id(object_id: str, revisions: CalculationRevisionCatalogue) -> str | None:
    revision = revisions.revisions.get(object_id)
    return None if revision is None else revision.work_unit_id


def _verification_event_work_unit_id(
    object_id: str,
    revisions: CalculationRevisionCatalogue,
    verification: VerificationReportCatalogue | None,
) -> str | None:
    report = None if verification is None else verification.get(object_id)
    if report is None:
        return None
    return _revision_event_work_unit_id(report.calculation_revision_id, revisions)


def _filing_event_work_unit_id(object_id: str, filings: ModeloRecordCatalogue) -> str | None:
    record = filings.records.get(object_id)
    return None if record is None else record.work_unit_id


def _declarations_lifecycle_facts(
    events: BucketEventHistoryCatalogue,
    *,
    work_units: WorkUnitCatalogue,
    revisions: CalculationRevisionCatalogue,
    verification: VerificationReportCatalogue | None,
    filings: ModeloRecordCatalogue,
) -> tuple[DeclarationsSanitizedLifecycleFactV1, ...]:
    """Project the persisted event log into the Declarations filing history.

    Only events whose declaration is still in the catalogue are reported: the
    workspace joins every fact to a live declaration address, and a fact for a
    work unit that is no longer there has no row to belong to.
    """
    known = {unit.work_unit_id for unit in work_units.values()}
    facts: list[DeclarationsSanitizedLifecycleFactV1] = []
    for event in sorted(events.events.values(), key=bucket_event_order_key):
        kind = _LIFECYCLE_KIND_BY_EVENT.get(event.event_type)
        if kind is None:
            continue
        work_unit_id = _lifecycle_work_unit_id(event, revisions=revisions, verification=verification, filings=filings)
        if work_unit_id is None or work_unit_id not in known:
            continue
        facts.append(
            DeclarationsSanitizedLifecycleFactV1(
                fact_id=event.event_id,
                work_unit_id=work_unit_id,
                occurred_at=event.occurred_at,
                kind=kind,
            )
        )
    return tuple(facts)


def _read_declarations_workspace(
    *,
    operation: PinnedAuthorityOperation,
    bucket_id: str,
    work_units: WorkUnitCatalogue,
    calculation_revisions: CalculationRevisionCatalogue,
    filing_records: ModeloRecordCatalogue,
    observed_at: UtcInstant,
    result_casilla_reader: DeclarationResultCasillaReaderV1 | None,
    lifecycle_facts: tuple[DeclarationsSanitizedLifecycleFactV1, ...] | None,
) -> DeclarationsWorkspaceProjectionV1 | None:
    history_observation = (
        DeclarationsWorkspaceZoneObservationV1(
            zone=DeclarationsWorkspaceZone.FILING_HISTORY,
            availability=DeclarationsWorkspaceAvailability.UNAVAILABLE,
            reason_code="workbench.declarations.lifecycle_reader_unavailable",
        )
        if lifecycle_facts is None
        else declarations_observation(DeclarationsWorkspaceZone.FILING_HISTORY, observed_at)
    )
    try:
        return project_declarations_portfolio(
            operation=operation,
            bucket_id=bucket_id,
            work_units=work_units,
            calculation_revisions=calculation_revisions,
            filing_records=filing_records,
            lifecycle_facts=() if lifecycle_facts is None else lifecycle_facts,
            result_casilla_reader=result_casilla_reader,
            zone_observations=(
                declarations_observation(DeclarationsWorkspaceZone.DECLARATIONS, observed_at),
                declarations_observation(DeclarationsWorkspaceZone.CALCULATION_REVISIONS, observed_at),
                history_observation,
            ),
        )
    except DeclarationsWorkspaceProjectionError:
        return None


def _invoice_catalogue_revision(
    ledger_revision: tuple[str, str] | None,
    ledger_sources: tuple[TransactionCatalogue, InvoiceCatalogue] | None,
) -> str:
    """Name the invoice catalogue the calendar's ledger signals were derived from.

    The store's own revision when it states one, otherwise the digest of the
    catalogue itself; ``unbound`` when no invoice store is bound.
    """
    if ledger_revision is not None:
        return ledger_revision[1]
    if ledger_sources is None:
        return "unbound"
    return content_hash_hex(ledger_sources[1].model_dump(mode="json"))


class _StoredCatalogues(NamedTuple):
    """What the profile's stores held when a capture began, with the revision each stated."""

    record: UserProfileRecord
    work_units: WorkUnitCatalogue
    work_units_revision: str
    revisions: CalculationRevisionCatalogue
    calculations_revision: str
    filings: ModeloRecordCatalogue
    filings_revision: str
    verification: VerificationReportCatalogue | None
    bucket_events: BucketEventHistoryCatalogue | None


@dataclass(frozen=True, slots=True)
class SecureProfileWorkbenchGenerationReadDoorV1:
    """Read one generation from explicit secure profile repositories.

    Every repository is session-bound by the child composition root. The door
    loads each authority once, projects only safe application DTOs, and marks
    authorities lacking an installed-session reader as unavailable instead of
    manufacturing empty fixtures.
    """

    profile_id: str
    operation: PinnedAuthorityOperation
    profile_repository: ProfileRecordReadRepositoryV1
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol
    filing_repository: ModeloRecordCatalogueRepositoryProtocol
    clock: Callable[[], UtcInstant]
    account_session_reader: Callable[[], HomeAccountSession] | None = None
    """The live account session Home shows; a declarations-list read is composed without one."""
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None
    verification_repository: VerificationReportCatalogueRepositoryProtocol | None = None
    reconciliation_reader: Callable[[], tuple[ModeloReconciliationRecord, ...]] | None = None
    notification_custody_reader: Callable[[], int] | None = None
    """Counts the notification documents this profile already holds locally.

    Unbound means this session did not read the store, which AEAT Sync reports
    as a composition gap -- distinct from a count of zero, which is a proven
    zero the operator can act on.
    """
    result_casilla_reader: DeclarationResultCasillaReaderV1 | None = None
    census_observation_reader: Callable[[], CensalObservation | None] | None = None
    """Names the casilla that settles one modelo revision, or nothing.

    Injected rather than resolved in the door, which holds repositories and no
    registry access. An unbound reader leaves every declaration's result
    unknown, which is the same honest absence a modelo with no declared
    settlement role produces -- not a zero.
    """
    operation_contracts: OperationPublicContractSetV1 | None = None
    modelo_projection_reader: Callable[[WorkUnit], ModeloWorkspaceProjectionV1] | None = None
    ledger_action_ports: LedgerActionPorts | None = None
    """Outer-composed ledger ports for this profile, when the ledger is bound."""
    capture_memory: WorkbenchCaptureMemory | None = None
    calendar_aeat_reader: Callable[[], CalendarEvidenceReadOutcome[AeatCalendarEvidenceSources]] | None = None
    """The session's reusable capture work; every capture recomputes everything without one."""
    """An absent reader below is a composition fact, not a data fact.

    A host that did not bind a ledger store or an operation contract set
    cannot observe those authorities, and the generation says so with an
    explicit refusal rather than publishing an empty workspace that would be
    indistinguishable from a profile holding nothing.
    """

    def read_workbench_generation_inputs(self) -> WorkbenchGenerationInputsV1:
        """Capture secure local facts once and build installed projections."""
        with diagnostic_scope(), _capture_phase("generation_inputs"):
            return self._capture_generation_inputs()

    def _capture_generation_inputs(self) -> WorkbenchGenerationInputsV1:
        account_session_reader = self.account_session_reader
        if account_session_reader is None:
            raise InternalInvariantError("a workbench generation needs the live account session")
        _timed("account_session", account_session_reader)
        observed_at = self.clock()
        as_of = observed_at.astimezone(ZoneInfo("Europe/Madrid")).date()
        (
            record,
            work_units,
            work_units_revision,
            revisions,
            calculations_revision,
            filings,
            filings_revision,
            verification,
            bucket_events,
        ) = self._load_stored_catalogues()
        declarations = self._read_declarations_projection(
            work_units=work_units,
            revisions=revisions,
            verification=verification,
            filings=filings,
            bucket_events=bucket_events,
            observed_at=observed_at,
        )
        raw_values = record_to_path_values(record)
        # The ledger is read before the calendar: its invoices answer the
        # ledger-derived obligation signals the calendar decides on.
        ledger_revision = _timed("ledger_revision", self._ledger_revision)
        ledger_sources = self._load_ledger_sources()
        aeat_evidence, aeat_projection = _timed(
            "calendar_aeat_evidence", lambda: self._read_calendar_aeat_evidence(raw_values)
        )
        calendar_inputs = self._read_calendar_inputs(
            record=record,
            raw_values=raw_values,
            aeat_evidence=aeat_evidence,
            aeat_projection=aeat_projection,
            as_of=as_of,
            work_units=work_units,
            filings=filings,
            observed_at=observed_at,
            operation=self.operation,
            work_units_revision=work_units_revision,
            filings_revision=filings_revision,
            ledger_revision=ledger_revision,
            ledger_sources=ledger_sources,
        )
        custody_count = _timed("custody_count", self._load_custody_count)
        census_observation = _timed("census_observation", self._load_census_observation)
        ledger_ports = self.ledger_action_ports
        ledger = (
            None
            if ledger_ports is None
            else _timed(
                "ledger_workspace",
                lambda: self._read_ledger(revisions.revisions, work_units, sources=ledger_sources, ports=ledger_ports),
            )
        )
        modelo = _timed(
            "modelo_workspaces",
            lambda: self._read_modelo(work_units),
            count=lambda projections: None if projections is None else len(projections),
        )
        aeat_sync, aeat_sync_refusal = _timed(
            "aeat_sync_workspace",
            lambda: self._read_aeat_sync(
                declared_tax_id(raw_values),
                observed_at=observed_at,
                filings=tuple(filings.records.values()),
                custody_count=custody_count,
                censo_values=raw_values,
                census_observation=census_observation,
                filed_evidence=aeat_projection,
            ),
        )
        account_session = _timed("account_session", account_session_reader)
        if not self._capture_is_unchanged(
            record=record,
            work_units_revision=work_units_revision,
            calculations_revision=calculations_revision,
            filings_revision=filings_revision,
            ledger_revision=ledger_revision,
            ledger_sources=ledger_sources,
            verification=verification,
            bucket_events=bucket_events,
            custody_count=custody_count,
            census_observation=census_observation,
        ):
            raise InternalInvariantError("secure workbench generation changed during capture")
        return _timed(
            "generation_assembly",
            lambda: build_workbench_generation_inputs(
                observed_at=observed_at,
                account_session=account_session,
                calendar_inputs=calendar_inputs,
                ledger=ledger,
                declarations=declarations,
                aeat_sync=aeat_sync,
                aeat_sync_refusal=aeat_sync_refusal,
                modelo=modelo,
                work_units=work_units,
                verification=verification,
            ),
        )

    def read_declaration_list_inputs(self) -> DeclarationListInputs:
        """Capture only what the declarations list joins: the local declarations and the legal calendar.

        It reads the same repositories, through the same projections, as a
        generation does, and is checked unchanged across the capture the same
        way, without the account session only Home needs.
        """
        with diagnostic_scope(), _capture_phase("declaration_list_inputs"):
            return self._capture_declaration_list_inputs()

    def _capture_declaration_list_inputs(self) -> DeclarationListInputs:
        observed_at = self.clock()
        as_of = observed_at.astimezone(ZoneInfo("Europe/Madrid")).date()
        (
            record,
            work_units,
            work_units_revision,
            revisions,
            calculations_revision,
            filings,
            filings_revision,
            verification,
            bucket_events,
        ) = self._load_stored_catalogues()
        declarations = self._read_declarations_projection(
            work_units=work_units,
            revisions=revisions,
            verification=verification,
            filings=filings,
            bucket_events=bucket_events,
            observed_at=observed_at,
        )
        raw_values = record_to_path_values(record)
        ledger_revision = _timed("ledger_revision", self._ledger_revision)
        ledger_sources = self._load_ledger_sources()
        aeat_evidence, aeat_projection = _timed(
            "calendar_aeat_evidence", lambda: self._read_calendar_aeat_evidence(raw_values)
        )
        calendar_inputs = self._read_calendar_inputs(
            record=record,
            raw_values=raw_values,
            aeat_evidence=aeat_evidence,
            aeat_projection=aeat_projection,
            as_of=as_of,
            work_units=work_units,
            filings=filings,
            observed_at=observed_at,
            operation=self.operation,
            work_units_revision=work_units_revision,
            filings_revision=filings_revision,
            ledger_revision=ledger_revision,
            ledger_sources=ledger_sources,
        )
        if not self._capture_is_unchanged(
            record=record,
            work_units_revision=work_units_revision,
            calculations_revision=calculations_revision,
            filings_revision=filings_revision,
            ledger_revision=ledger_revision,
            ledger_sources=ledger_sources,
            verification=verification,
            bucket_events=bucket_events,
            custody_count=_timed("custody_count", self._load_custody_count),
            census_observation=_timed("census_observation", self._load_census_observation),
        ):
            raise InternalInvariantError("secure declarations list changed during capture")
        return DeclarationListInputs(workspace=declarations, calendar=calendar_inputs.declarations_calendar)

    def _read_declarations_projection(
        self,
        *,
        work_units: WorkUnitCatalogue,
        revisions: CalculationRevisionCatalogue,
        verification: VerificationReportCatalogue | None,
        filings: ModeloRecordCatalogue,
        bucket_events: BucketEventHistoryCatalogue | None,
        observed_at: UtcInstant,
    ) -> DeclarationsWorkspaceProjectionV1 | None:
        lifecycle_facts = (
            None
            if bucket_events is None
            else _timed(
                "lifecycle_facts",
                lambda: _declarations_lifecycle_facts(
                    bucket_events,
                    work_units=work_units,
                    revisions=revisions,
                    verification=verification,
                    filings=filings,
                ),
                count=len,
            )
        )
        declarations = _timed(
            "declarations_portfolio",
            lambda: _read_declarations_workspace(
                operation=self.operation,
                bucket_id=self.profile_id,
                work_units=work_units,
                calculation_revisions=revisions,
                filing_records=filings,
                observed_at=observed_at,
                result_casilla_reader=self.result_casilla_reader,
                lifecycle_facts=lifecycle_facts,
            ),
            count=lambda workspace: None if workspace is None else len(workspace.declarations),
        )
        if declarations is None:
            return None
        current_ids = {unit.current_calculation_revision_id for unit in work_units.values()}
        current_revisions = {key: value for key, value in revisions.revisions.items() if key in current_ids}
        with _capture_phase("declaration_summaries") as measured:
            measured["item_count"] = len(declarations.declarations)
            return declarations.model_copy(
                update={
                    "declarations": tuple(
                        ref.model_copy(
                            update={
                                "summary": ref.summary
                                or declaration_summary(
                                    ref,
                                    revisions=current_revisions,
                                    verification=verification,
                                    operation=self.operation,
                                )
                            }
                        )
                        for ref in declarations.declarations
                    )
                }
            )

    def _read_calendar_aeat_evidence(
        self, raw_values: Mapping[str, str]
    ) -> tuple[CalendarEvidenceReadOutcome[AeatCalendarEvidenceSources], CalendarEvidenceProjection]:
        """Read stored AEAT filing captures once for the calendar and AEAT Sync.

        Both surfaces project the same retained observations through one
        evidence join, scoped to the profile's declared tax identity.
        """
        aeat_evidence = (
            unbound_calendar_aeat_evidence()
            if self.calendar_aeat_reader is None or declared_tax_id(raw_values) is None
            else self.calendar_aeat_reader()
        )
        aeat_projection = build_calendar_evidence_projection(
            local=CalendarEvidenceReadOutcome(
                state=HomeZoneState(availability=HomeAvailability.AVAILABLE),
                value=LocalCalendarEvidenceSources(),
            ),
            aeat=aeat_evidence,
            expected_tax_id=declared_tax_id(raw_values),
        )
        return aeat_evidence, aeat_projection

    def _read_calendar_inputs(
        self,
        *,
        record: UserProfileRecord,
        raw_values: Mapping[str, str],
        aeat_evidence: CalendarEvidenceReadOutcome[AeatCalendarEvidenceSources],
        aeat_projection: CalendarEvidenceProjection,
        as_of: date,
        work_units: WorkUnitCatalogue,
        filings: ModeloRecordCatalogue,
        observed_at: UtcInstant,
        operation: PinnedAuthorityOperation,
        work_units_revision: str,
        filings_revision: str,
        ledger_revision: tuple[str, str] | None,
        ledger_sources: tuple[TransactionCatalogue, InvoiceCatalogue] | None,
    ) -> WorkbenchCalendarInputs:
        with _capture_phase("calendar_memo_key"):
            memo = CalendarMemo(
                memory=self.capture_memory,
                key=WorkbenchCalendarMemoKey(
                    profile_content_digest=record.content_digest,
                    work_units_revision=work_units_revision,
                    filings_revision=filings_revision,
                    as_of=as_of,
                    generation=operation.generation,
                    aeat_evidence_revision=content_hash_hex(
                        {
                            "state": aeat_evidence.state.model_dump(mode="json"),
                            "evidence": [row.model_dump(mode="json") for row in aeat_projection.evidence],
                        }
                    ),
                    invoice_catalogue_revision=_invoice_catalogue_revision(ledger_revision, ledger_sources),
                ),
            )
        return _timed(
            "calendar_inputs",
            lambda: read_workbench_calendar_inputs(
                record=record,
                raw_values=raw_values,
                as_of=as_of,
                work_units=work_units,
                filings=filings,
                observed_at=observed_at,
                operation=operation,
                aeat_evidence=aeat_evidence,
                invoice_source_ports=loaded_invoice_source_ports(None if ledger_sources is None else ledger_sources[1]),
                memo=memo,
            ),
        )

    def _capture_is_unchanged(
        self,
        *,
        record: UserProfileRecord,
        work_units_revision: str,
        calculations_revision: str,
        filings_revision: str,
        ledger_revision: tuple[str, str] | None,
        ledger_sources: tuple[TransactionCatalogue, InvoiceCatalogue] | None,
        verification: VerificationReportCatalogue | None,
        bucket_events: BucketEventHistoryCatalogue | None,
        custody_count: int | None,
        census_observation: CensalObservation | None = None,
    ) -> bool:
        with _capture_phase("recheck"):
            final_record = _timed("recheck_profile_record", lambda: self.profile_repository.load(self.profile_id))
            _, final_work_units_revision = _timed("recheck_work_units", self.work_unit_repository.load_revisioned)
            _, final_calculations_revision = _timed(
                "recheck_calculation_revisions",
                lambda: self.calculation_repository.load_revisioned(operation=self.operation),
            )
            _, final_filings_revision = _timed("recheck_filings", self.filing_repository.load_revisioned)
            return (
                final_record.content_digest == record.content_digest
                and final_work_units_revision == work_units_revision
                and final_calculations_revision == calculations_revision
                and final_filings_revision == filings_revision
                and _timed("recheck_ledger", lambda: self._ledger_is_unchanged(ledger_revision, ledger_sources))
                and _timed("recheck_verification_reports", self._load_verification_reports) == verification
                and _timed("recheck_bucket_events", self._load_bucket_events) == bucket_events
                and _timed("recheck_custody_count", self._load_custody_count) == custody_count
                and _timed("recheck_census_observation", self._load_census_observation) == census_observation
            )

    def _load_stored_catalogues(self) -> _StoredCatalogues:
        """Read the profile record and every catalogue a capture joins, each as its own timed phase."""
        record = _timed("profile_record", lambda: self.profile_repository.load(self.profile_id))
        work_units, work_units_revision = _timed(
            "work_units", self.work_unit_repository.load_revisioned, count=lambda loaded: len(loaded[0].work_units)
        )
        revisions, calculations_revision = _timed(
            "calculation_revisions",
            lambda: self.calculation_repository.load_revisioned(operation=self.operation),
            count=lambda loaded: len(loaded[0].revisions),
        )
        filings, filings_revision = _timed(
            "filings", self.filing_repository.load_revisioned, count=lambda loaded: len(loaded[0].records)
        )
        verification = _timed(
            "verification_reports",
            self._load_verification_reports,
            count=lambda reports: None if reports is None else len(reports.reports),
        )
        bucket_events = _timed(
            "bucket_events",
            self._load_bucket_events,
            count=lambda events: None if events is None else len(events.events),
        )
        return _StoredCatalogues(
            record,
            work_units,
            work_units_revision,
            revisions,
            calculations_revision,
            filings,
            filings_revision,
            verification,
            bucket_events,
        )

    def _load_bucket_events(self) -> BucketEventHistoryCatalogue | None:
        """Read the bucket event log, or nothing when no host bound one."""
        return None if self.bucket_event_repository is None else self.bucket_event_repository.load()

    def _load_census_observation(self) -> CensalObservation | None:
        """Read the stored census observation, or nothing when no host bound a reader."""
        return None if self.census_observation_reader is None else self.census_observation_reader()

    def _ledger_revision(self) -> tuple[str, str] | None:
        """State both ledger stores' revisions without decrypting them, when both can.

        Read before the catalogues themselves, so a write landing between the
        two reads shows up as a changed revision at the close of the capture.
        ``None`` means a store cannot state one, and the close compares the
        decoded catalogues instead.
        """
        ports = self.ledger_action_ports
        if ports is None:
            return None
        transactions, invoices = ports.transaction_repository, ports.invoice_repository
        if not isinstance(transactions, RevisionedCatalogueStore) or not isinstance(invoices, RevisionedCatalogueStore):
            return None
        transaction_revision, invoice_revision = transactions.load_revision(), invoices.load_revision()
        if transaction_revision is None or invoice_revision is None:
            return None
        return transaction_revision, invoice_revision

    def _ledger_is_unchanged(
        self,
        revision: tuple[str, str] | None,
        sources: tuple[TransactionCatalogue, InvoiceCatalogue] | None,
    ) -> bool:
        if revision is not None:
            return self._ledger_revision() == revision
        return self._load_ledger_sources(phase_prefix="recheck_") == sources

    def _load_custody_count(self) -> int | None:
        """Count documents in local custody, or nothing when no reader is bound.

        Read inside the capture window and re-read at its close like every
        other source: a document landing mid-capture would otherwise let AEAT
        Sync publish a count that was never true at any single instant.
        """
        if self.notification_custody_reader is None:
            return None
        return self.notification_custody_reader()

    def _load_verification_reports(self) -> VerificationReportCatalogue | None:
        """Read the verification catalogue, or nothing when no host bound one.

        Loaded inside the capture window and re-read at its close like every
        other source, because a report that lands mid-capture would let Home
        offer work against a blocker that no longer exists.
        """
        if self.verification_repository is None:
            return None
        return require_verification_report_coordinates_current(
            self.verification_repository.load(),
            operation=self.operation,
        )

    def _load_ledger_sources(self, *, phase_prefix: str = "") -> tuple[TransactionCatalogue, InvoiceCatalogue] | None:
        """Read the ledger stores once, as the value the guard compares.

        Neither store exposes a revision handle the way the work-unit,
        calculation and filing catalogues do, so the snapshot itself is the
        identity: an equal pair means nothing was written between the two
        reads. Bucket events are deliberately outside it -- they only supply
        review context and have no whole-catalogue read to compare.
        """
        ports = self.ledger_action_ports
        if ports is None:
            return None
        return (
            _timed(
                f"{phase_prefix}ledger_transactions",
                ports.transaction_repository.load,
                count=lambda catalogue: len(catalogue.transactions),
            ),
            _timed(
                f"{phase_prefix}ledger_invoices",
                ports.invoice_repository.load,
                count=lambda catalogue: len(catalogue.invoices),
            ),
        )

    def _read_ledger(
        self,
        calculation_revisions: Mapping[str, CalculationRevision],
        work_units: WorkUnitCatalogue,
        *,
        sources: tuple[TransactionCatalogue, InvoiceCatalogue] | None,
        ports: LedgerActionPorts,
    ) -> LedgerWorkspaceProjectionV1 | None:
        """Project the Ledger workspace only when its stores were bound."""
        if sources is None:
            return None
        from .ledger.workspace_reader import read_ledger_workspace_projection

        return read_ledger_workspace_projection(
            bucket_id=self.profile_id,
            ports=ports,
            calculation_revisions=calculation_revisions,
            work_units=work_units,
            transactions=sources[0],
            invoices=sources[1],
        )

    def _read_modelo(self, work_units: WorkUnitCatalogue) -> tuple[ModeloWorkspaceProjectionV1, ...] | None:
        """Project every current work unit, or refuse the whole Modelo source.

        A profile holding no work yields an empty tuple, which is a proven
        empty portfolio rather than an unread one.

        A unit the bundled registry cannot inspect refuses the SOURCE, not the
        session: a partial tuple would silently omit a declaration the profile
        holds, and letting the failure escape would take Home, Ledger,
        Declarations and AEAT Sync down with it for one unsupported modelo.
        """
        if self.modelo_projection_reader is None:
            return None
        reader = self.modelo_projection_reader
        try:
            return tuple(reader(unit) for unit in work_units.values())
        except (ValueError, LookupError):
            return None

    def _read_aeat_sync(
        self,
        subject_key: str | None,
        *,
        observed_at: UtcInstant,
        filings: tuple[ModeloRecord, ...],
        custody_count: int | None,
        censo_values: Mapping[str, object],
        census_observation: CensalObservation | None = None,
        filed_evidence: CalendarEvidenceProjection | None = None,
    ) -> tuple[AeatSyncWorkspaceProjectionV1 | None, NamespacedId]:
        """Project the pre-pull AEAT Sync workspace against composed contracts.

        A profile carrying no NIF has no subject to scope AEAT evidence to.
        Scoping it to the schema's placeholder would produce a workspace whose
        rows a later real pull would refuse as a mixed subject, so the source
        stays unavailable until the profile declares its identity.

        A malformed local projection is likewise a source refusal.  The
        workspace projector remains the boundary that detects it, while this
        installed-session reader prevents one rejected AEAT Sync projection
        from preventing Home and the other workbench sources from rendering.
        Its projector-specific refusal stays distinct from the missing-reader
        refusal so downstream source, admission, and search semantics retain
        the actual cause.
        """
        if self.operation_contracts is None or subject_key is None:
            return None, _AEAT_SYNC_READER_UNAVAILABLE
        from .aeat_sync.workspace_reader import read_local_aeat_sync_workspace_projection

        try:
            return (
                read_local_aeat_sync_workspace_projection(
                    bucket_id=self.profile_id,
                    subject_key=subject_key,
                    observed_at=observed_at,
                    filings=filings,
                    operation_contracts=self.operation_contracts,
                    custody_count=custody_count,
                    censo_values={key: value for key, value in censo_values.items() if isinstance(value, str)},
                    census_observation=census_observation,
                    filed_evidence=filed_evidence,
                    reconciliations=None if self.reconciliation_reader is None else self.reconciliation_reader(),
                ),
                _AEAT_SYNC_READER_UNAVAILABLE,
            )
        except AeatSyncWorkspaceProjectionError as error:
            _LOGGER.warning("AEAT Sync workspace projection refused: %s", error)
            return None, _AEAT_SYNC_SNAPSHOT_PROJECTOR_UNAVAILABLE
        except ValidationError as error:
            # Field locations and error types only: the rejected input values are private.
            _LOGGER.warning(
                "AEAT Sync workspace projection failed validation: %s",
                [(detail["loc"], detail["type"]) for detail in error.errors()],
            )
            return None, _AEAT_SYNC_SNAPSHOT_PROJECTOR_UNAVAILABLE
