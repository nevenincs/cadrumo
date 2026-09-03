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
from enum import StrEnum
from typing import Literal, Protocol, Self

from pydantic import BaseModel, model_validator

from ..core.identifier_grammar import NamespacedId
from ..core.models import STRICT_FROZEN_CONFIG
from ..core.time.utc import UtcInstant
from .aeat_sync.workspace import AeatSyncWorkspaceProjectionV1
from .ledger.workspace import LedgerWorkspaceProjectionV1
from .modelo.declarations_calendar import DeclarationsCalendarProjectionV1
from .modelo.declarations_workspace import DeclarationsWorkspaceProjectionV1
from .modelo.workspace_models import ModeloWorkspaceProjectionV1
from .overview.home import HomeProjectionInput, HomeProjectionV1, compose_home_projection
from .search.installed_workbench import (
    InstalledWorkbenchSearchSnapshotV1,
    assemble_installed_workbench_search_snapshot,
)
from .search.workbench import WorkbenchDestinationAdmission

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
            (self.ledger_admission, "workbench.ledger"),
            (self.declarations_admission, "workbench.declarations"),
            (self.aeat_sync_admission, "workbench.aeat_sync"),
        )
        for admission, destination in expected:
            if admission.destination != destination:
                raise ValueError(f"generation search admission must target {destination!r}")
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
    "WorkbenchGenerationAvailability",
    "WorkbenchGenerationInputsV1",
    "WorkbenchGenerationProjectionResultV1",
    "WorkbenchGenerationReadDoorV1",
    "WorkbenchGenerationSourceResultV1",
    "WorkbenchGenerationV1",
    "assemble_workbench_generation",
    "assemble_workbench_generation_from",
]
