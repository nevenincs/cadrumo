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

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal

from .aeat_sync.workspace import AeatSyncWorkspaceProjectionV1
from .ledger.workspace import (
    LedgerWorkspaceProjectionV1,
)
from .modelo.declarations_workspace_contracts import DeclarationsWorkspaceProjectionV1
from .modelo.workspace_models import (
    ModeloWorkspaceProjectionV1,
)
from .overview.home import (
    HomeProjectionInput,
    HomeProjectionV1,
    compose_home_projection,
)
from .search.installed_workbench import (
    InstalledWorkbenchSearchSnapshotV1,
    assemble_installed_workbench_search_snapshot,
)
from .search.workbench import WorkbenchDestinationAdmission
from .workbench_generation_contracts import (
    WorkbenchGenerationAvailability,
    WorkbenchGenerationInputsV1,
    WorkbenchGenerationProjectionResultV1,
    WorkbenchGenerationReadDoorV1,
    WorkbenchGenerationSourceResultV1,
    WorkbenchGenerationV1,
)

WORKBENCH_GENERATION_CONTRACT_VERSION: Literal[1] = 1

_AEAT_SYNC_READER_UNAVAILABLE: Final[str] = "workbench.aeat_sync.reader_unavailable"
_AEAT_SYNC_SNAPSHOT_PROJECTOR_UNAVAILABLE: Final[str] = "workbench.aeat_sync.snapshot_projector_unavailable"


if TYPE_CHECKING:
    pass


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
    search = assemble_workbench_generation_search(
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


def _search_projections(
    sources: tuple[
        WorkbenchGenerationProjectionResultV1[LedgerWorkspaceProjectionV1],
        WorkbenchGenerationProjectionResultV1[DeclarationsWorkspaceProjectionV1],
        WorkbenchGenerationProjectionResultV1[AeatSyncWorkspaceProjectionV1],
        WorkbenchGenerationProjectionResultV1[tuple[ModeloWorkspaceProjectionV1, ...]],
    ],
) -> (
    tuple[
        LedgerWorkspaceProjectionV1,
        DeclarationsWorkspaceProjectionV1,
        AeatSyncWorkspaceProjectionV1,
        tuple[ModeloWorkspaceProjectionV1, ...],
    ]
    | None
):
    if any(source.projection is None for source in sources):
        return None
    ledger_projection = sources[0].projection
    declarations_projection = sources[1].projection
    aeat_projection = sources[2].projection
    modelo_projection = sources[3].projection
    # The ``None`` branch above makes these values present; the explicit
    # narrowing keeps the call boundary honest for static type checkers.
    if (
        ledger_projection is None
        or declarations_projection is None
        or aeat_projection is None
        or modelo_projection is None
    ):  # pragma: no cover - guarded by the branch above
        return None
    return ledger_projection, declarations_projection, aeat_projection, modelo_projection


def _search_availability(
    sources: tuple[
        WorkbenchGenerationProjectionResultV1[LedgerWorkspaceProjectionV1],
        WorkbenchGenerationProjectionResultV1[DeclarationsWorkspaceProjectionV1],
        WorkbenchGenerationProjectionResultV1[AeatSyncWorkspaceProjectionV1],
        WorkbenchGenerationProjectionResultV1[tuple[ModeloWorkspaceProjectionV1, ...]],
    ],
) -> WorkbenchGenerationAvailability:
    if any(source.availability is WorkbenchGenerationAvailability.STALE for source in sources):
        return WorkbenchGenerationAvailability.STALE
    return WorkbenchGenerationAvailability.AVAILABLE


def assemble_workbench_generation_search(
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
    projections = _search_projections(sources)
    if projections is None:
        return _missing_search(sources)
    ledger_projection, declarations_projection, aeat_projection, modelo_projection = projections
    availability = _search_availability(sources)
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
    "InstalledWorkbenchGenerationProviderV1",
    "assemble_workbench_generation",
    "assemble_workbench_generation_from",
    "assemble_workbench_generation_search",
]
