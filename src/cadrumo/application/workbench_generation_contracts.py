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

from enum import StrEnum
from typing import TYPE_CHECKING, Final, Literal, Protocol, Self

from pydantic import BaseModel, model_validator

from ..core.errors.hierarchy import pydantic_validation_boundary
from ..core.identifier_grammar import NamespacedId
from ..core.models import STRICT_FROZEN_CONFIG
from ..core.time.utc import UtcInstant
from ..domain.user_profile.values import UserProfileRecord
from .aeat_sync.workspace import AeatSyncWorkspaceProjectionV1
from .ledger.workspace import (
    LedgerWorkspaceProjectionV1,
)
from .modelo.declarations_calendar import (
    DeclarationsCalendarProjectionV1,
)
from .modelo.declarations_workspace_contracts import DeclarationsWorkspaceProjectionV1
from .modelo.workspace_models import (
    ModeloWorkspaceProjectionV1,
)
from .overview.home import (
    HomeProjectionInput,
    HomeProjectionV1,
)
from .search.installed_workbench import (
    InstalledWorkbenchSearchSnapshotV1,
)
from .search.workbench import WorkbenchDestinationAdmission, WorkbenchDestinationAdmissionState

WORKBENCH_GENERATION_CONTRACT_VERSION: Literal[1] = 1

_AEAT_SYNC_READER_UNAVAILABLE: Final[str] = "workbench.aeat_sync.reader_unavailable"
_AEAT_SYNC_SNAPSHOT_PROJECTOR_UNAVAILABLE: Final[str] = "workbench.aeat_sync.snapshot_projector_unavailable"


if TYPE_CHECKING:
    pass


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
        _validate_observable_result_state(availability, observed_at, refusal, has_value, label)
        return
    _validate_unobservable_result_state(availability, observed_at, refusal, has_value, label)


def _validate_observable_result_state(
    availability: WorkbenchGenerationAvailability,
    observed_at: UtcInstant | None,
    refusal: NamespacedId | None,
    has_value: bool,
    label: str,
) -> None:
    if observed_at is None:
        raise ValueError(f"{label} {availability.value} result requires an observation time")
    if availability is WorkbenchGenerationAvailability.AVAILABLE and refusal is not None:
        raise ValueError(f"{label} available result cannot carry a refusal")
    if not has_value:
        raise ValueError(f"{label} {availability.value} result requires a value")
    if availability is WorkbenchGenerationAvailability.STALE and refusal is None:
        raise ValueError(f"{label} stale result requires a refusal")


def _validate_unobservable_result_state(
    availability: WorkbenchGenerationAvailability,
    observed_at: UtcInstant | None,
    refusal: NamespacedId | None,
    has_value: bool,
    label: str,
) -> None:
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
    @pydantic_validation_boundary
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
    @pydantic_validation_boundary
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
    @pydantic_validation_boundary
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
