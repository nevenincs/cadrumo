"""What the workbench asks of the application, supplied by the composition root.

The screen holds no repository, registry or operation service. It is handed an
object that answers these questions, calls it off the event loop, and renders
the answers. Each answer is a frozen application read model, so the screen can
never observe it change mid-render.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

from .....application.modelo.casilla_help import ModeloCasillaHelpCardV1
from .....application.modelo.work_form_models import ModeloFormAddressV1, ModeloFormField, ModeloFormScalar
from .....application.modelo.work_form_service import ModeloWorkFormLoadV1
from .....core.casilla_id import CasillaId
from .....core.external_constants import OutputLanguage
from .....core.modelo_export_artefact import ModeloExportArtefact
from .....core.payment_election import PaymentElection
from .....core.prior_domiciliation_election import PriorDomiciliationElection
from .....core.refund_election import RefundElection
from ..m303_evidence import OrdinaryM303FilingEvidenceSubmission

if TYPE_CHECKING:
    from .....application.modelo.export_projection import ModeloExportPublicResultV3
    from .....application.operations.frontend_projection import OperationPublicProjectionV1
    from ...operations.controller_port import OperationControllerPort


class ModeloWorkbenchReaderV1(Protocol):
    """Reads one declaration's form and the help of its casillas."""

    def load(self, language: OutputLanguage) -> ModeloWorkFormLoadV1:
        """Read the declaration's current form in ``language``."""
        ...

    def help_card(self, casilla_id: CasillaId, language: OutputLanguage) -> ModeloCasillaHelpCardV1:
        """Assemble the mechanical help of one casilla in ``language``."""
        ...

    def edit_refusal(self) -> str | None:
        """Why the declaration last read cannot be edited, in the filer's words; ``None`` when it can."""
        ...


class WorkbenchChangeKind(StrEnum):
    """What one staged change asks the application to do with an address."""

    #: Declare this value.
    SET = "set"
    #: Remove the value the filer declared; nothing replaces it.
    CLEAR = "clear"
    #: Stop replacing the source's value; the source wins again.
    RESTORE = "restore"


@dataclass(frozen=True, slots=True)
class WorkbenchChange:
    """One staged change, addressed semantically and typed, never a raw lexeme."""

    address: ModeloFormAddressV1
    kind: WorkbenchChangeKind
    value: ModeloFormScalar = None


@dataclass(frozen=True, slots=True)
class WorkbenchParsed:
    """A lexeme the application read as a typed value, and how that value reads back."""

    value: ModeloFormScalar
    display: str


@dataclass(frozen=True, slots=True)
class WorkbenchRefused:
    """A lexeme the application could not read, with a sentence saying how to fix it."""

    message: str


type WorkbenchParseOutcome = WorkbenchParsed | WorkbenchRefused


@dataclass(frozen=True, slots=True)
class WorkbenchFinding:
    """One thing the check before applying found, in the filer's words.

    ``address`` is the field the finding concerns, or ``None`` when it concerns
    the whole submission. A blocking finding would make the application refuse
    the changes, so they cannot be applied until it is resolved.
    """

    address: ModeloFormAddressV1 | None
    message: str
    blocking: bool


@dataclass(frozen=True, slots=True)
class WorkbenchPreflight:
    """What the application found when it checked the staged changes before they are applied.

    ``stale`` means the declaration changed since the workbench read it, so the
    changes must be checked again against what it holds now. ``operator_entries_unknown``
    means the declaration does not record which of its values the filer typed.
    """

    findings: tuple[WorkbenchFinding, ...] = ()
    stale: bool = False
    operator_entries_unknown: bool = False


@dataclass(frozen=True, slots=True)
class WorkbenchApplyPrerequisite:
    """A failed Apply's named source, without changing the saved form's values."""

    address: ModeloFormAddressV1
    calculation_revision_id: str | None
    source_boxes: tuple[CasillaId, ...] = ()


@dataclass(frozen=True, slots=True)
class WorkbenchCalculationEvidence:
    """What a calculation must first ask the filer: the ordinary Modelo 303 filing answers."""

    work_unit_id: str
    asks_modelo_390: bool


@dataclass(frozen=True, slots=True)
class WorkbenchExportOffer:
    """The exports this installation can publish, and whether the declaration asks payment elections."""

    artefacts: tuple[ModeloExportArtefact, ...]
    asks_elections: bool


@dataclass(frozen=True, slots=True)
class WorkbenchExportRequest:
    """One export the filer asked for, with every election set, never blank."""

    output_path: str
    artefact: ModeloExportArtefact
    refund_election: RefundElection
    payment_election: PaymentElection
    prior_domiciliation_election: PriorDomiciliationElection
    replace_existing: bool


class ModeloWorkbenchActionsV1(Protocol):
    """Parses the filer's typing and runs the declaration's operations."""

    def parse(self, field: ModeloFormField, lexeme: str, language: OutputLanguage) -> WorkbenchParseOutcome:
        """Read what the filer typed for one field, in the language they typed it in."""
        ...

    async def preflight(self, changes: tuple[WorkbenchChange, ...]) -> WorkbenchPreflight:
        """Check the staged changes against the declaration as it stands, without applying them."""
        ...

    async def apply(self, changes: tuple[WorkbenchChange, ...]) -> OperationControllerPort:
        """Submit the staged changes and recalculate, through the supervised operation."""
        ...

    async def take_apply_prerequisite(self) -> WorkbenchApplyPrerequisite | None:
        """Read, once, the source a refused Apply named, after it settles."""
        ...

    def calculation_evidence(self) -> WorkbenchCalculationEvidence | None:
        """What the next calculation must first ask the filer, or ``None`` when it asks nothing."""
        ...

    async def calculate(
        self, m303_evidence: OrdinaryM303FilingEvidenceSubmission | None = None
    ) -> OperationControllerPort:
        """Recalculate the declaration, keeping the filer's values, with the answers it asked for."""
        ...

    async def verify(self) -> OperationControllerPort:
        """Verify the current calculation."""
        ...

    async def file(self) -> OperationControllerPort:
        """Record the verified calculation as filed locally."""
        ...

    def export_offer(self) -> WorkbenchExportOffer:
        """The exports on offer for this declaration."""
        ...

    async def export(self, request: WorkbenchExportRequest) -> OperationControllerPort:
        """Export the verified calculation as the filer asked."""
        ...

    async def export_result(self, projection: OperationPublicProjectionV1) -> ModeloExportPublicResultV3 | None:
        """The facts of one settled export, or ``None`` when they cannot be read."""
        ...

    def refresh_product(self) -> None:
        """Have the rest of the product read the declaration afresh after an operation changed it."""
        ...


__all__ = [
    "ModeloWorkbenchActionsV1",
    "ModeloWorkbenchReaderV1",
    "WorkbenchApplyPrerequisite",
    "WorkbenchCalculationEvidence",
    "WorkbenchChange",
    "WorkbenchChangeKind",
    "WorkbenchExportOffer",
    "WorkbenchExportRequest",
    "WorkbenchFinding",
    "WorkbenchParseOutcome",
    "WorkbenchParsed",
    "WorkbenchPreflight",
    "WorkbenchRefused",
]
