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
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Literal, Protocol, Self
from zoneinfo import ZoneInfo

from pydantic import BaseModel, model_validator

from ..core.identifier_grammar import NamespacedId
from ..core.models import STRICT_FROZEN_CONFIG
from ..core.time.utc import UtcInstant
from ..domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ..domain.invoices.models import InvoiceCatalogue
from ..domain.invoices.protocols import InvoiceCatalogueRepositoryProtocol
from ..domain.modelos.calculation_revision import CalculationRevision
from ..domain.modelos.filing_record import ModeloRecord
from ..domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
)
from ..domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue
from ..domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ..domain.transactions.models import TransactionCatalogue
from ..domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..domain.user_profile.values import UserProfileRecord
from .aeat_sync.workspace import AeatSyncWorkspaceProjectionV1
from .ledger.workspace import LedgerWorkspaceProjectionV1
from .modelo.declarations_calendar import (
    DeclarationsCalendarProjectionV1,
    DeclarationsCalendarSource,
    DeclarationsCalendarSourceObservationV1,
    project_declarations_calendar,
)
from .modelo.declarations_workspace import (
    DeclarationsWorkspaceAvailability,
    DeclarationsWorkspaceProjectionV1,
    DeclarationsWorkspaceZone,
    DeclarationsWorkspaceZoneObservationV1,
    project_declarations_workspace,
)
from .modelo.workspace_models import ModeloWorkspaceProjectionV1
from .operations.registry import OperationPublicContractSetV1
from .overview.calendar import build_overview_calendar
from .overview.calendar_models import OverviewCalendar, OverviewCalendarRange
from .overview.evidence import (
    AeatCalendarEvidenceSources,
    CalendarEvidenceReadOutcome,
    LocalCalendarEvidenceSources,
    build_calendar_evidence_projection,
)
from .overview.home import (
    HomeAccountSession,
    HomeAvailability,
    HomeProjectionInput,
    HomeProjectionV1,
    HomeZoneState,
    compose_home_projection,
)
from .search.installed_workbench import (
    InstalledWorkbenchSearchSnapshotV1,
    assemble_installed_workbench_search_snapshot,
)
from .search.workbench import WorkbenchDestinationAdmission, WorkbenchDestinationAdmissionState
from .user_profile.projections import projection_for_taxpayer, record_to_path_values

WORKBENCH_GENERATION_CONTRACT_VERSION: Literal[1] = 1


class WorkbenchGenerationAvailability(StrEnum):
    """Truthful state of one already-captured source result."""

    AVAILABLE = "available"
    STALE = "stale"
    LOCKED = "locked"
    NEVER_CAPTURED = "never_captured"
    UNAVAILABLE = "unavailable"


_OBSERVABLE = frozenset(
    {
        WorkbenchGenerationAvailability.AVAILABLE,
        WorkbenchGenerationAvailability.STALE,
    }
)


def _validate_result_state(
    *,
    availability: WorkbenchGenerationAvailability,
    observed_at: UtcInstant | None,
    refusal: NamespacedId | None,
    has_value: bool,
    label: str,
) -> None:
    """Enforce the no-false-empty state machine shared by input/output rows."""
    if availability in _OBSERVABLE:
        if observed_at is None:
            raise ValueError(f"{label} {availability.value} result requires an observation time")
        if availability is WorkbenchGenerationAvailability.AVAILABLE and refusal is not None:
            raise ValueError(f"{label} available result cannot carry a refusal")
        if not has_value:
            raise ValueError(f"{label} {availability.value} result requires a value")
        if availability is WorkbenchGenerationAvailability.STALE and refusal is None:
            raise ValueError(f"{label} stale result requires a refusal")
        return
    if observed_at is not None:
        raise ValueError(f"{label} {availability.value} result cannot carry an observation time")
    if refusal is None:
        raise ValueError(f"{label} {availability.value} result requires a refusal")
    if has_value:
        raise ValueError(f"{label} {availability.value} result cannot carry a value")


class WorkbenchGenerationSourceResultV1[SourceT](BaseModel):
    """Typed result admitted from one preloaded application read door.

    ``value`` is input-only: it is either a safe ``HomeProjectionInput`` or an
    already-built safe workspace projection.  The assembler copies only the
    resulting projection into :class:`WorkbenchGenerationV1`.
    """

    model_config = STRICT_FROZEN_CONFIG

    availability: WorkbenchGenerationAvailability
    observed_at: UtcInstant | None = None
    refusal: NamespacedId | None = None
    value: SourceT | None = None

    @model_validator(mode="after")
    def _state_is_truthful(self) -> Self:
        _validate_result_state(
            availability=self.availability,
            observed_at=self.observed_at,
            refusal=self.refusal,
            has_value=self.value is not None,
            label="source",
        )
        return self

    @classmethod
    def available(cls, value: SourceT, *, observed_at: UtcInstant) -> Self:
        """Construct a source result with a measured value."""
        return cls(availability=WorkbenchGenerationAvailability.AVAILABLE, observed_at=observed_at, value=value)

    @classmethod
    def stale(cls, value: SourceT, *, observed_at: UtcInstant, refusal: NamespacedId) -> Self:
        """Construct a source result retaining a known but stale value."""
        return cls(
            availability=WorkbenchGenerationAvailability.STALE,
            observed_at=observed_at,
            refusal=refusal,
            value=value,
        )

    @classmethod
    def locked(cls, *, refusal: NamespacedId) -> Self:
        """Construct a source result blocked by local custody."""
        return cls(availability=WorkbenchGenerationAvailability.LOCKED, refusal=refusal)

    @classmethod
    def never_captured(cls, *, refusal: NamespacedId) -> Self:
        """Construct a source result for a source not read in this session."""
        return cls(availability=WorkbenchGenerationAvailability.NEVER_CAPTURED, refusal=refusal)

    @classmethod
    def unavailable(cls, *, refusal: NamespacedId) -> Self:
        """Construct a source result whose reader cannot currently answer."""
        return cls(availability=WorkbenchGenerationAvailability.UNAVAILABLE, refusal=refusal)


class WorkbenchGenerationProjectionResultV1[ProjectionT](BaseModel):
    """One immutable safe projection plus its source availability evidence."""

    model_config = STRICT_FROZEN_CONFIG

    availability: WorkbenchGenerationAvailability
    observed_at: UtcInstant | None = None
    refusal: NamespacedId | None = None
    projection: ProjectionT | None = None

    @model_validator(mode="after")
    def _state_is_truthful(self) -> Self:
        _validate_result_state(
            availability=self.availability,
            observed_at=self.observed_at,
            refusal=self.refusal,
            has_value=self.projection is not None,
            label="projection",
        )
        return self


class WorkbenchGenerationInputsV1(BaseModel):
    """One coherent set of preloaded public inputs for child composition.

    Ledger, Declarations, AEAT Sync, and Modelo inputs are already safe
    projection results.  The Home input is the existing safe composer input so
    this boundary can reuse ``compose_home_projection`` without accepting any
    repository or source adapter.
    """

    model_config = STRICT_FROZEN_CONFIG

    assembled_at: UtcInstant
    home: WorkbenchGenerationSourceResultV1[HomeProjectionInput]
    ledger: WorkbenchGenerationSourceResultV1[LedgerWorkspaceProjectionV1]
    declarations: WorkbenchGenerationSourceResultV1[DeclarationsWorkspaceProjectionV1]
    declarations_calendar: WorkbenchGenerationSourceResultV1[DeclarationsCalendarProjectionV1]
    aeat_sync: WorkbenchGenerationSourceResultV1[AeatSyncWorkspaceProjectionV1]
    modelo: WorkbenchGenerationSourceResultV1[tuple[ModeloWorkspaceProjectionV1, ...]]
    ledger_admission: WorkbenchDestinationAdmission
    declarations_admission: WorkbenchDestinationAdmission
    aeat_sync_admission: WorkbenchDestinationAdmission

    @model_validator(mode="after")
    def _search_admissions_are_canonical(self) -> Self:
        expected = (
            (self.ledger, self.ledger_admission, "workbench.ledger"),
            (self.declarations, self.declarations_admission, "workbench.declarations"),
            (self.aeat_sync, self.aeat_sync_admission, "workbench.aeat_sync"),
        )
        for source, admission, destination in expected:
            if admission.destination != destination:
                raise ValueError(f"generation search admission must target {destination!r}")
            expected_state = WorkbenchDestinationAdmissionState(source.availability.value)
            if admission.state is not expected_state:
                raise ValueError(f"{destination} admission must match its source availability")
        if (
            self.declarations_admission.state
            in {WorkbenchDestinationAdmissionState.AVAILABLE, WorkbenchDestinationAdmissionState.STALE}
            and self.declarations_calendar.value is None
        ):
            raise ValueError("available Declarations admission requires its calendar projection")
        return self


class WorkbenchGenerationV1(BaseModel):
    """Immutable public generation consumed by an installed workbench root."""

    model_config = STRICT_FROZEN_CONFIG

    contract_version: Literal[1] = WORKBENCH_GENERATION_CONTRACT_VERSION
    assembled_at: UtcInstant
    home: WorkbenchGenerationProjectionResultV1[HomeProjectionV1]
    ledger: WorkbenchGenerationProjectionResultV1[LedgerWorkspaceProjectionV1]
    declarations: WorkbenchGenerationProjectionResultV1[DeclarationsWorkspaceProjectionV1]
    declarations_calendar: WorkbenchGenerationProjectionResultV1[DeclarationsCalendarProjectionV1]
    aeat_sync: WorkbenchGenerationProjectionResultV1[AeatSyncWorkspaceProjectionV1]
    modelo: WorkbenchGenerationProjectionResultV1[tuple[ModeloWorkspaceProjectionV1, ...]]
    search: WorkbenchGenerationProjectionResultV1[InstalledWorkbenchSearchSnapshotV1]
    ledger_admission: WorkbenchDestinationAdmission
    declarations_admission: WorkbenchDestinationAdmission
    aeat_sync_admission: WorkbenchDestinationAdmission


class WorkbenchGenerationReadDoorV1(Protocol):
    """Injected child-composition door returning one already-loaded generation."""

    def read_workbench_generation_inputs(self) -> WorkbenchGenerationInputsV1:
        """Return one coherent, preloaded input set without frontend work."""
        ...


class ProfileRecordReadRepositoryV1(Protocol):
    """Narrow read-only door for the current encrypted profile record."""

    def load(self, profile_id: str) -> UserProfileRecord:
        """Load the record served by the already-open custody session."""
        ...


@dataclass(frozen=True, slots=True)
class SecureProfileWorkbenchGenerationReadDoorV1:
    """Read one generation from explicit secure profile repositories.

    Every repository is session-bound by the child composition root. The door
    loads each authority once, projects only safe application DTOs, and marks
    authorities lacking an installed-session reader as unavailable instead of
    manufacturing empty fixtures.
    """

    profile_id: str
    profile_repository: ProfileRecordReadRepositoryV1
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol
    filing_repository: ModeloRecordCatalogueRepositoryProtocol
    clock: Callable[[], UtcInstant]
    account_session_reader: Callable[[], HomeAccountSession]
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None
    operation_contracts: OperationPublicContractSetV1 | None = None
    modelo_projection_reader: Callable[[WorkUnit], ModeloWorkspaceProjectionV1] | None = None
    """An absent reader below is a composition fact, not a data fact.

    A host that did not bind a ledger store or an operation contract set
    cannot observe those authorities, and the generation says so with an
    explicit refusal rather than publishing an empty workspace that would be
    indistinguishable from a profile holding nothing.
    """

    def read_workbench_generation_inputs(self) -> WorkbenchGenerationInputsV1:
        """Capture secure local facts once and build installed projections."""
        self.account_session_reader()
        observed_at = self.clock()
        as_of = observed_at.astimezone(ZoneInfo("Europe/Madrid")).date()
        record = self.profile_repository.load(self.profile_id)
        work_units, work_units_revision = self.work_unit_repository.load_revisioned()
        revisions, calculations_revision = self.calculation_repository.load_revisioned()
        filings, filings_revision = self.filing_repository.load_revisioned()

        declarations = project_declarations_workspace(
            bucket_id=self.profile_id,
            work_units=work_units,
            calculation_revisions=revisions,
            filing_records=filings,
            lifecycle_facts=(),
            zone_observations=(
                _declarations_observation(DeclarationsWorkspaceZone.DECLARATIONS, observed_at),
                _declarations_observation(DeclarationsWorkspaceZone.CALCULATION_REVISIONS, observed_at),
                DeclarationsWorkspaceZoneObservationV1(
                    zone=DeclarationsWorkspaceZone.FILING_HISTORY,
                    availability=DeclarationsWorkspaceAvailability.UNAVAILABLE,
                    reason_code="workbench.declarations.lifecycle_reader_unavailable",
                ),
            ),
        )
        taxpayer = projection_for_taxpayer(record, tax_id_default="00000000T")
        raw_values = record_to_path_values(record)
        query_range = OverviewCalendarRange(
            from_date=date(as_of.year, 1, 1),
            to_date=date(as_of.year, 12, 31),
        )
        schedule_calendar = build_overview_calendar(
            taxpayer,
            query_range,
            today=as_of,
            raw_values=raw_values,
            work_units=tuple(work_units.values()),
        )
        evidence = build_calendar_evidence_projection(
            local=CalendarEvidenceReadOutcome(
                state=HomeZoneState(availability=HomeAvailability.AVAILABLE, observed_at=observed_at),
                value=LocalCalendarEvidenceSources(
                    filing_records=_scope_filing_records(
                        tuple(filings.records.values()),
                        schedule_calendar,
                    )
                ),
            ),
            aeat=CalendarEvidenceReadOutcome[AeatCalendarEvidenceSources](
                state=HomeZoneState(
                    availability=HomeAvailability.NEVER_CAPTURED,
                    reason_code="workbench.calendar.aeat_reader_unavailable",
                ),
            ),
            expected_tax_id=taxpayer.tax_id,
        )
        calendar = build_overview_calendar(
            taxpayer,
            query_range,
            today=as_of,
            raw_values=raw_values,
            filing_evidence=evidence.evidence,
            work_units=tuple(work_units.values()),
        )
        declarations_calendar = project_declarations_calendar(
            calendar=calendar,
            evidence=evidence,
            as_of=as_of,
            schedule_observation=_schedule_observation(calendar, observed_at),
        )
        ledger_sources = self._load_ledger_sources()
        ledger = self._read_ledger(revisions.revisions, work_units, sources=ledger_sources)
        modelo = self._read_modelo(work_units)
        aeat_sync = self._read_aeat_sync(
            _declared_tax_id(raw_values),
            observed_at=observed_at,
            filing_count=len(filings.records),
        )
        account_session = self.account_session_reader()
        final_record = self.profile_repository.load(self.profile_id)
        _, final_work_units_revision = self.work_unit_repository.load_revisioned()
        _, final_calculations_revision = self.calculation_repository.load_revisioned()
        _, final_filings_revision = self.filing_repository.load_revisioned()
        if (
            final_record.content_digest != record.content_digest
            or final_work_units_revision != work_units_revision
            or final_calculations_revision != calculations_revision
            or final_filings_revision != filings_revision
            or self._load_ledger_sources() != ledger_sources
        ):
            raise RuntimeError("secure workbench generation changed during capture")
        return WorkbenchGenerationInputsV1(
            assembled_at=observed_at,
            home=WorkbenchGenerationSourceResultV1[HomeProjectionInput].available(
                _secure_profile_home_input(
                    observed_at=observed_at,
                    account_session=account_session,
                ),
                observed_at=observed_at,
            ),
            ledger=(
                WorkbenchGenerationSourceResultV1[LedgerWorkspaceProjectionV1].available(
                    ledger, observed_at=observed_at
                )
                if ledger is not None
                else WorkbenchGenerationSourceResultV1[LedgerWorkspaceProjectionV1].unavailable(
                    refusal="workbench.ledger.snapshot_projector_unavailable"
                )
            ),
            declarations=WorkbenchGenerationSourceResultV1[DeclarationsWorkspaceProjectionV1].available(
                declarations, observed_at=observed_at
            ),
            declarations_calendar=WorkbenchGenerationSourceResultV1[DeclarationsCalendarProjectionV1].available(
                declarations_calendar,
                observed_at=observed_at,
            ),
            aeat_sync=(
                WorkbenchGenerationSourceResultV1[AeatSyncWorkspaceProjectionV1].available(
                    aeat_sync, observed_at=observed_at
                )
                if aeat_sync is not None
                else WorkbenchGenerationSourceResultV1[AeatSyncWorkspaceProjectionV1].unavailable(
                    refusal="workbench.aeat_sync.reader_unavailable"
                )
            ),
            modelo=(
                WorkbenchGenerationSourceResultV1[tuple[ModeloWorkspaceProjectionV1, ...]].available(
                    modelo, observed_at=observed_at
                )
                if modelo is not None
                else WorkbenchGenerationSourceResultV1[tuple[ModeloWorkspaceProjectionV1, ...]].unavailable(
                    refusal="workbench.modelo.bulk_reader_unavailable"
                )
            ),
            ledger_admission=(
                _generation_admission("workbench.ledger", WorkbenchDestinationAdmissionState.AVAILABLE)
                if ledger is not None
                else _generation_admission(
                    "workbench.ledger",
                    WorkbenchDestinationAdmissionState.UNAVAILABLE,
                    reason_code="workbench.ledger.snapshot_projector_unavailable",
                )
            ),
            declarations_admission=_generation_admission(
                "workbench.declarations", WorkbenchDestinationAdmissionState.AVAILABLE
            ),
            aeat_sync_admission=(
                _generation_admission("workbench.aeat_sync", WorkbenchDestinationAdmissionState.AVAILABLE)
                if aeat_sync is not None
                else _generation_admission(
                    "workbench.aeat_sync",
                    WorkbenchDestinationAdmissionState.UNAVAILABLE,
                    reason_code="workbench.aeat_sync.reader_unavailable",
                )
            ),
        )

    def _load_ledger_sources(self) -> tuple[TransactionCatalogue, InvoiceCatalogue] | None:
        """Read the ledger stores once, as the value the guard compares.

        Neither store exposes a revision handle the way the work-unit,
        calculation and filing catalogues do, so the snapshot itself is the
        identity: an equal pair means nothing was written between the two
        reads. Bucket events are deliberately outside it -- they only supply
        review context and have no whole-catalogue read to compare.
        """
        if self.transaction_repository is None or self.invoice_repository is None:
            return None
        return (self.transaction_repository.load(), self.invoice_repository.load())

    def _read_ledger(
        self,
        calculation_revisions: Mapping[str, CalculationRevision],
        work_units: WorkUnitCatalogue,
        *,
        sources: tuple[TransactionCatalogue, InvoiceCatalogue] | None,
    ) -> LedgerWorkspaceProjectionV1 | None:
        """Project the Ledger workspace only when its stores were bound."""
        if self.transaction_repository is None or self.invoice_repository is None or sources is None:
            return None
        from .ledger.workspace_reader import read_ledger_workspace_projection

        return read_ledger_workspace_projection(
            bucket_id=self.profile_id,
            transaction_repository=self.transaction_repository,
            invoice_repository=self.invoice_repository,
            bucket_event_repository=self.bucket_event_repository,
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
        filing_count: int,
    ) -> AeatSyncWorkspaceProjectionV1 | None:
        """Project the pre-pull AEAT Sync workspace against composed contracts.

        A profile carrying no NIF has no subject to scope AEAT evidence to.
        Scoping it to the schema's placeholder would produce a workspace whose
        rows a later real pull would refuse as a mixed subject, so the source
        stays unavailable until the profile declares its identity.
        """
        if self.operation_contracts is None or subject_key is None:
            return None
        from .aeat_sync.workspace_reader import read_local_aeat_sync_workspace_projection

        return read_local_aeat_sync_workspace_projection(
            bucket_id=self.profile_id,
            subject_key=subject_key,
            observed_at=observed_at,
            filing_count=filing_count,
            operation_contracts=self.operation_contracts,
        )


def _declared_tax_id(raw_values: Mapping[str, object]) -> str | None:
    """Return the profile's own NIF, never the schema's placeholder default."""
    declared = raw_values.get("identity.tax_id")
    if not isinstance(declared, str) or not declared.strip():
        return None
    return declared.strip()


def _declarations_observation(
    zone: DeclarationsWorkspaceZone,
    observed_at: UtcInstant,
) -> DeclarationsWorkspaceZoneObservationV1:
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
            reason_code="workbench.calendar.taxpayer_model_undeclared",
        )
    return DeclarationsCalendarSourceObservationV1(
        source=DeclarationsCalendarSource.SCHEDULE,
        availability=HomeAvailability.AVAILABLE,
        observed_at=observed_at,
    )


def _secure_profile_home_input(*, observed_at: UtcInstant, account_session: HomeAccountSession) -> HomeProjectionInput:
    def unavailable(reason_code: str) -> HomeZoneState:
        return HomeZoneState(availability=HomeAvailability.UNAVAILABLE, reason_code=reason_code)

    return HomeProjectionInput(
        generated_at=observed_at,
        account=account_session,
        actions_state=unavailable("workbench.home.actions_projector_unavailable"),
        declarations_state=unavailable("workbench.home.declarations_resume_projector_unavailable"),
        ledger_state=unavailable("workbench.ledger.snapshot_projector_unavailable"),
        agenda_state=unavailable("workbench.home.agenda_projector_unavailable"),
        agenda_evidence_state=unavailable("workbench.calendar.aeat_reader_unavailable"),
        messages_state=unavailable("workbench.home.messages_reader_unavailable"),
    )


def _generation_admission(
    destination: str,
    state: WorkbenchDestinationAdmissionState,
    *,
    reason_code: str | None = None,
) -> WorkbenchDestinationAdmission:
    return WorkbenchDestinationAdmission(destination=destination, state=state, reason_code=reason_code)


@dataclass(frozen=True, slots=True)
class InstalledWorkbenchGenerationProviderV1:
    """Child-owned provider for one immutable installed-session generation.

    The read door is composed with secure repositories and application
    projectors by the process owner.  Calling the provider captures that door
    once and immediately discards its source bundle after projection.
    """

    read_door: WorkbenchGenerationReadDoorV1

    def __call__(self) -> WorkbenchGenerationV1:
        """Capture and assemble exactly one coherent generation."""
        return assemble_workbench_generation_from(self.read_door)


@dataclass(frozen=True, slots=True)
class CallableWorkbenchGenerationReadDoorV1:
    """Small typed adapter for a preloaded input callable.

    This value only invokes the supplied function.  It does not choose a
    repository, open storage, contact a backend, or invent a timestamp.
    """

    read: Callable[[], WorkbenchGenerationInputsV1]

    def read_workbench_generation_inputs(self) -> WorkbenchGenerationInputsV1:
        """Read the caller-owned, already-composed input bundle once."""
        return self.read()


def assemble_workbench_generation(inputs: WorkbenchGenerationInputsV1) -> WorkbenchGenerationV1:
    """Build one immutable generation from already-loaded public inputs.

    No area is changed into a known empty projection when its source result is
    missing.  Search is assembled only when every required projection exists;
    otherwise its own result preserves the strongest truthful source refusal.
    """
    home = _project_home(inputs.home)
    ledger = _carry_projection(inputs.ledger)
    declarations = _carry_projection(inputs.declarations)
    declarations_calendar = _carry_projection(inputs.declarations_calendar)
    aeat_sync = _carry_projection(inputs.aeat_sync)
    modelo = _carry_projection(inputs.modelo)
    search = _assemble_search(
        ledger=ledger,
        declarations=declarations,
        aeat_sync=aeat_sync,
        modelo=modelo,
        ledger_admission=inputs.ledger_admission,
        declarations_admission=inputs.declarations_admission,
        aeat_sync_admission=inputs.aeat_sync_admission,
    )
    return WorkbenchGenerationV1(
        assembled_at=inputs.assembled_at,
        home=home,
        ledger=ledger,
        declarations=declarations,
        declarations_calendar=declarations_calendar,
        aeat_sync=aeat_sync,
        modelo=modelo,
        search=search,
        ledger_admission=inputs.ledger_admission,
        declarations_admission=inputs.declarations_admission,
        aeat_sync_admission=inputs.aeat_sync_admission,
    )


def assemble_workbench_generation_from(read_door: WorkbenchGenerationReadDoorV1) -> WorkbenchGenerationV1:
    """Assemble one generation by invoking an injected read door exactly once."""
    return assemble_workbench_generation(read_door.read_workbench_generation_inputs())


def _project_home(
    source: WorkbenchGenerationSourceResultV1[HomeProjectionInput],
) -> WorkbenchGenerationProjectionResultV1[HomeProjectionV1]:
    if source.value is None:
        return WorkbenchGenerationProjectionResultV1(
            availability=source.availability,
            observed_at=source.observed_at,
            refusal=source.refusal,
        )
    projection = compose_home_projection(source.value)
    return WorkbenchGenerationProjectionResultV1(
        availability=source.availability,
        observed_at=source.observed_at,
        refusal=source.refusal,
        projection=projection,
    )


def _carry_projection[ProjectionT](
    source: WorkbenchGenerationSourceResultV1[ProjectionT],
) -> WorkbenchGenerationProjectionResultV1[ProjectionT]:
    """Copy an already-built safe projection without retaining input wrappers."""
    return WorkbenchGenerationProjectionResultV1(
        availability=source.availability,
        observed_at=source.observed_at,
        refusal=source.refusal,
        projection=source.value,
    )


def _assemble_search(
    *,
    ledger: WorkbenchGenerationProjectionResultV1[LedgerWorkspaceProjectionV1],
    declarations: WorkbenchGenerationProjectionResultV1[DeclarationsWorkspaceProjectionV1],
    aeat_sync: WorkbenchGenerationProjectionResultV1[AeatSyncWorkspaceProjectionV1],
    modelo: WorkbenchGenerationProjectionResultV1[tuple[ModeloWorkspaceProjectionV1, ...]],
    ledger_admission: WorkbenchDestinationAdmission,
    declarations_admission: WorkbenchDestinationAdmission,
    aeat_sync_admission: WorkbenchDestinationAdmission,
) -> WorkbenchGenerationProjectionResultV1[InstalledWorkbenchSearchSnapshotV1]:
    """Derive search from the same source generation or preserve refusal."""
    sources = (ledger, declarations, aeat_sync, modelo)
    if any(source.projection is None for source in sources):
        return _missing_search(sources)

    ledger_projection = ledger.projection
    declarations_projection = declarations.projection
    aeat_projection = aeat_sync.projection
    modelo_projection = modelo.projection
    # The ``None`` branch above makes these values present; the explicit
    # narrowing keeps the call boundary honest for static type checkers.
    if (
        ledger_projection is None
        or declarations_projection is None
        or aeat_projection is None
        or modelo_projection is None
    ):  # pragma: no cover - guarded by the branch above
        return _missing_search(sources)
    availability = (
        WorkbenchGenerationAvailability.STALE
        if any(source.availability is WorkbenchGenerationAvailability.STALE for source in sources)
        else WorkbenchGenerationAvailability.AVAILABLE
    )
    observed_at = min(source.observed_at for source in sources if source.observed_at is not None)
    refusal = next(
        (source.refusal for source in sources if source.availability is WorkbenchGenerationAvailability.STALE),
        None,
    )
    snapshot = assemble_installed_workbench_search_snapshot(
        ledger=ledger_projection,
        declarations=declarations_projection,
        aeat_sync=aeat_projection,
        modelo=modelo_projection,
        ledger_admission=ledger_admission,
        declarations_admission=declarations_admission,
        aeat_sync_admission=aeat_sync_admission,
    )
    return WorkbenchGenerationProjectionResultV1(
        availability=availability,
        observed_at=observed_at,
        refusal=refusal,
        projection=snapshot,
    )


def _missing_search(
    sources: tuple[
        WorkbenchGenerationProjectionResultV1[LedgerWorkspaceProjectionV1],
        WorkbenchGenerationProjectionResultV1[DeclarationsWorkspaceProjectionV1],
        WorkbenchGenerationProjectionResultV1[AeatSyncWorkspaceProjectionV1],
        WorkbenchGenerationProjectionResultV1[tuple[ModeloWorkspaceProjectionV1, ...]],
    ],
) -> WorkbenchGenerationProjectionResultV1[InstalledWorkbenchSearchSnapshotV1]:
    """Collapse missing search dependencies without claiming an empty index."""
    missing = tuple(source for source in sources if source.projection is None)
    states = tuple(source.availability for source in missing)
    if all(state is WorkbenchGenerationAvailability.NEVER_CAPTURED for state in states):
        availability = WorkbenchGenerationAvailability.NEVER_CAPTURED
    elif all(
        state in {WorkbenchGenerationAvailability.LOCKED, WorkbenchGenerationAvailability.NEVER_CAPTURED}
        for state in states
    ):
        availability = WorkbenchGenerationAvailability.LOCKED
    else:
        availability = WorkbenchGenerationAvailability.UNAVAILABLE
    refusal = next(source.refusal for source in missing if source.refusal is not None)
    return WorkbenchGenerationProjectionResultV1(availability=availability, refusal=refusal)


__all__ = [
    "CallableWorkbenchGenerationReadDoorV1",
    "InstalledWorkbenchGenerationProviderV1",
    "ProfileRecordReadRepositoryV1",
    "SecureProfileWorkbenchGenerationReadDoorV1",
    "WorkbenchGenerationAvailability",
    "WorkbenchGenerationInputsV1",
    "WorkbenchGenerationProjectionResultV1",
    "WorkbenchGenerationReadDoorV1",
    "WorkbenchGenerationSourceResultV1",
    "WorkbenchGenerationV1",
    "assemble_workbench_generation",
    "assemble_workbench_generation_from",
]
