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

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Literal, Protocol, Self, cast

from pydantic import BaseModel, model_validator

from ..core.identifier_grammar import NamespacedId
from ..core.models import STRICT_FROZEN_CONFIG
from ..core.time.utc import UtcInstant
from ..domain.invoices.protocols import InvoiceCatalogueRepositoryProtocol
from ..domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
)
from ..domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ..domain.transactions.models import TransactionCatalogue
from ..domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..domain.user_profile.values import UserProfileRecord
from .aeat_sync.workspace import AeatSyncWorkspaceProjectionV1
from .ledger.actions_manual import ledger_transaction_payload, summarize_manual_transactions
from .ledger.models import LedgerReviewQuery
from .ledger.review_projection import project_ledger_review_query
from .ledger.workspace import LedgerWorkspaceProjectionV1, project_ledger_workspace
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
from .overview.calendar import build_overview_calendar
from .overview.calendar_models import OverviewCalendarRange
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
    HomeSessionPosture,
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
    profile_label: str
    profile_expires_at: UtcInstant
    profile_repository: ProfileRecordReadRepositoryV1
    transaction_repository: TransactionCatalogueRepositoryProtocol
    invoice_repository: InvoiceCatalogueRepositoryProtocol
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol
    filing_repository: ModeloRecordCatalogueRepositoryProtocol
    clock: Callable[[], UtcInstant]
    today: Callable[[], date]

    def read_workbench_generation_inputs(self) -> WorkbenchGenerationInputsV1:
        """Capture secure local facts once and build installed projections."""
        observed_at = self.clock()
        as_of = self.today()
        record = self.profile_repository.load(self.profile_id)
        transactions = self.transaction_repository.load()
        invoices = self.invoice_repository.load()
        work_units = self.work_unit_repository.load()
        revisions = self.calculation_repository.load()
        filings = self.filing_repository.load()

        summary = summarize_manual_transactions(
            bucket_id=self.profile_id,
            transaction_repository=cast(
                TransactionCatalogueRepositoryProtocol,
                _LoadedTransactionCatalogue(self.profile_id, transactions),
            ),
        )
        review = project_ledger_review_query(
            LedgerReviewQuery(bucket_id=self.profile_id),
            catalogue=transactions,
            bucket_event_repository=None,
            transaction_payload_builder=ledger_transaction_payload,
        )
        ledger = project_ledger_workspace(
            summary=summary,
            preflight=None,
            review=review,
            transactions=transactions,
            invoices=invoices,
            revisions=revisions.revisions,
            work_units=work_units,
        )
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
        calendar = build_overview_calendar(
            taxpayer,
            query_range,
            today=as_of,
            raw_values=raw_values,
            filing_evidence=(),
            work_units=tuple(work_units.values()),
        )
        evidence = build_calendar_evidence_projection(
            local=CalendarEvidenceReadOutcome(
                state=HomeZoneState(availability=HomeAvailability.AVAILABLE, observed_at=observed_at),
                value=LocalCalendarEvidenceSources(filing_records=tuple(filings.records.values())),
            ),
            aeat=CalendarEvidenceReadOutcome[AeatCalendarEvidenceSources](
                state=HomeZoneState(
                    availability=HomeAvailability.NEVER_CAPTURED,
                    reason_code="workbench.calendar.aeat_reader_unavailable",
                ),
            ),
            expected_tax_id=taxpayer.tax_id,
        )
        declarations_calendar = project_declarations_calendar(
            calendar=calendar,
            evidence=evidence,
            as_of=as_of,
            schedule_observation=DeclarationsCalendarSourceObservationV1(
                source=DeclarationsCalendarSource.SCHEDULE,
                availability=HomeAvailability.AVAILABLE,
                observed_at=observed_at,
            ),
        )
        return WorkbenchGenerationInputsV1(
            assembled_at=observed_at,
            home=WorkbenchGenerationSourceResultV1[HomeProjectionInput].available(
                _secure_profile_home_input(
                    observed_at=observed_at,
                    profile_label=self.profile_label,
                    expires_at=self.profile_expires_at,
                ),
                observed_at=observed_at,
            ),
            ledger=WorkbenchGenerationSourceResultV1[LedgerWorkspaceProjectionV1].available(
                ledger, observed_at=observed_at
            ),
            declarations=WorkbenchGenerationSourceResultV1[DeclarationsWorkspaceProjectionV1].available(
                declarations, observed_at=observed_at
            ),
            declarations_calendar=WorkbenchGenerationSourceResultV1[DeclarationsCalendarProjectionV1].available(
                declarations_calendar,
                observed_at=observed_at,
            ),
            aeat_sync=WorkbenchGenerationSourceResultV1[AeatSyncWorkspaceProjectionV1].unavailable(
                refusal="workbench.aeat_sync.reader_unavailable"
            ),
            modelo=WorkbenchGenerationSourceResultV1[tuple[ModeloWorkspaceProjectionV1, ...]].unavailable(
                refusal="workbench.modelo.bulk_reader_unavailable"
            ),
            ledger_admission=_generation_admission("workbench.ledger", WorkbenchDestinationAdmissionState.AVAILABLE),
            declarations_admission=_generation_admission(
                "workbench.declarations", WorkbenchDestinationAdmissionState.AVAILABLE
            ),
            aeat_sync_admission=_generation_admission(
                "workbench.aeat_sync",
                WorkbenchDestinationAdmissionState.UNAVAILABLE,
                reason_code="workbench.aeat_sync.reader_unavailable",
            ),
        )


@dataclass(frozen=True, slots=True)
class _LoadedTransactionCatalogue:
    """Snapshot reader preventing a second secure read during projection."""

    bucket_id: str
    catalogue: TransactionCatalogue

    def load(self) -> TransactionCatalogue:
        """Return the already-loaded immutable catalogue."""
        return self.catalogue


def _declarations_observation(
    zone: DeclarationsWorkspaceZone,
    observed_at: UtcInstant,
) -> DeclarationsWorkspaceZoneObservationV1:
    return DeclarationsWorkspaceZoneObservationV1(
        zone=zone,
        availability=DeclarationsWorkspaceAvailability.AVAILABLE,
        observed_at=observed_at,
    )


def _secure_profile_home_input(
    *, observed_at: UtcInstant, profile_label: str, expires_at: UtcInstant
) -> HomeProjectionInput:
    unavailable = HomeZoneState(
        availability=HomeAvailability.UNAVAILABLE,
        reason_code="workbench.home.reader_unavailable",
    )
    return HomeProjectionInput(
        generated_at=observed_at,
        account=HomeAccountSession(
            posture=HomeSessionPosture.ACTIVE,
            profile_label=profile_label,
            expires_at=expires_at,
        ),
        actions_state=unavailable,
        declarations_state=unavailable,
        ledger_state=unavailable,
        agenda_state=unavailable,
        agenda_evidence_state=unavailable,
        messages_state=unavailable,
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
