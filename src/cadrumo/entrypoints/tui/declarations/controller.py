"""Pure controller and common shell for the Declarations workspace."""

from __future__ import annotations

from typing import ClassVar, Final, cast

from textual.binding import Binding
from textual.message import Message
from textual.screen import Screen
from textual.widgets import DataTable, Static

from ....application.modelo.declarations_workspace import (
    DECLARATIONS_WORKSPACE_CONTRACT_VERSION,
    DeclarationsWorkspaceAvailability,
    DeclarationsWorkspaceProjectionV1,
    DeclarationsWorkspaceZone,
    DeclarationsWorkspaceZoneStateV1,
)
from ....application.operator_actions.catalogue import lookup_action
from ....application.operator_actions.models import ActionReference
from ....core.i18n.render import tr
from ....domain.modelos.calculation_revision import CalculationRevisionState
from ....domain.modelos.filing_record import ExternalEvidenceKind, ModeloRecordStatus
from ....domain.modelos.work_unit import WorkUnitState
from ..components.theme import BASE_CSS, tokenised
from ..navigation import TuiScreenContextV1
from .models import (
    DeclarationHandoffV1,
    DeclarationsDestinationIdV1,
    DeclarationsRouteTargetV1,
    FilingHandoffV1,
    RevisionHandoffV1,
)

_ZONE_BY_DESTINATION: Final = {
    "declarations.overview": DeclarationsWorkspaceZone.DECLARATIONS,
    "declarations.revisions": DeclarationsWorkspaceZone.CALCULATION_REVISIONS,
    "declarations.filing_history": DeclarationsWorkspaceZone.FILING_HISTORY,
    "declarations.modelo_workspace": DeclarationsWorkspaceZone.DECLARATIONS,
}
_DESTINATION_KEYS: Final = {
    "declarations.overview": "tui.declarations.destination.overview",
    "declarations.revisions": "tui.declarations.destination.revisions",
    "declarations.filing_history": "tui.declarations.destination.filing_history",
    "declarations.modelo_workspace": "tui.declarations.destination.modelo_workspace",
}
_AVAILABILITY_KEYS: Final = {
    DeclarationsWorkspaceAvailability.AVAILABLE: "tui.declarations.availability.available",
    DeclarationsWorkspaceAvailability.LOCKED: "tui.declarations.availability.locked",
    DeclarationsWorkspaceAvailability.STALE: "tui.declarations.availability.stale",
    DeclarationsWorkspaceAvailability.NEVER_CAPTURED: "tui.declarations.availability.never_captured",
    DeclarationsWorkspaceAvailability.UNAVAILABLE: "tui.declarations.availability.unavailable",
}
_WORK_STATE_KEYS: Final = {state: f"tui.declarations.work_state.{state.value}" for state in WorkUnitState}
_REVISION_STATE_KEYS: Final = {
    state: f"tui.declarations.revision_state.{state.value}" for state in CalculationRevisionState
}
_FILING_STATE_KEYS: Final = {
    ModeloRecordStatus.VIGENTE: "tui.declarations.filing_state.vigente",
    ModeloRecordStatus.SUPERSEDIDO: "tui.declarations.filing_state.supersedido",
}
_EVIDENCE_KEYS: Final = {
    ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF: "tui.declarations.evidence.aeat_justificante_pdf",
    ExternalEvidenceKind.AEAT_LIVE_CAPTURE: "tui.declarations.evidence.aeat_live_capture",
}


def declarations_copy(key: str, **values: object) -> str:
    """Resolve authored display copy through the canonical catalogue."""
    return tr(key, **values)


def natural_address(modelo: object, year: object, period: object) -> str:
    """Render the public Modelo/year/period coordinate."""
    token = getattr(period, "registry_token", str(period))
    return f"Modelo {modelo} · {year} · {token}"


def availability_label(value: DeclarationsWorkspaceAvailability) -> str:
    return declarations_copy(_AVAILABILITY_KEYS[value])


def work_state_label(value: WorkUnitState) -> str:
    return declarations_copy(_WORK_STATE_KEYS[value])


def revision_state_label(value: CalculationRevisionState) -> str:
    return declarations_copy(_REVISION_STATE_KEYS[value])


def filing_state_label(value: ModeloRecordStatus) -> str:
    return declarations_copy(_FILING_STATE_KEYS[value])


def evidence_label(value: ExternalEvidenceKind | None) -> str:
    return declarations_copy("tui.declarations.evidence.none") if value is None else declarations_copy(_EVIDENCE_KEYS[value])


class DeclarationsWorkspaceController:
    """Custody of an injected safe projection and admitted read references."""

    def __init__(
        self,
        context: TuiScreenContextV1,
        projection: DeclarationsWorkspaceProjectionV1,
        *,
        work_action: ActionReference,
        revisions_action: ActionReference,
        filing_action: ActionReference,
        declaration_handoff: DeclarationHandoffV1 | None = None,
        revision_handoff: RevisionHandoffV1 | None = None,
        filing_handoff: FilingHandoffV1 | None = None,
    ) -> None:
        if context.destination != "workbench.declarations":
            raise ValueError("Declarations workspace requires the workbench.declarations context")
        if projection.contract_version != DECLARATIONS_WORKSPACE_CONTRACT_VERSION:
            raise ValueError("unsupported Declarations workspace projection contract")
        expected = (
            (work_action, "modelo.work.list"),
            (revisions_action, "modelo.work.revisions"),
            (filing_action, "modelo.filing_record.list"),
        )
        for action, command in expected:
            if lookup_action(action.action_id).target_command_key != command:
                raise ValueError("injected Declarations read action resolves to another application door")
        self.context = context
        self.projection = projection
        self.work_action = work_action
        self.revisions_action = revisions_action
        self.filing_action = filing_action
        self.declaration_handoff = declaration_handoff
        self.revision_handoff = revision_handoff
        self.filing_handoff = filing_handoff

    def zone_state(self, zone: DeclarationsWorkspaceZone) -> DeclarationsWorkspaceZoneStateV1:
        return next(item for item in self.projection.zones if item.zone is zone)

    def target(self, destination: DeclarationsDestinationIdV1) -> DeclarationsRouteTargetV1:
        return DeclarationsRouteTargetV1(destination=destination, zone=_ZONE_BY_DESTINATION[destination])

    def restored_id(self, semantic_key: str) -> str | None:
        focus = self.context.focus
        return focus.restore_token if focus is not None and focus.semantic_key == semantic_key else None


class DeclarationsWorkspaceScreen(Screen[None]):
    """One-scroll host-neutral shell with semantic internal navigation."""

    BINDINGS: ClassVar = [Binding("escape", "back", "", show=False)]
    CSS = BASE_CSS + tokenised(
        """
        .declarations-page { width: 100%; height: 1fr; }
        .declarations-refusal { color: $warning; text-style: bold; height: auto; }
        """
    )

    def __init__(self, controller: DeclarationsWorkspaceController, *, id: str) -> None:
        super().__init__(id=id)
        self.controller = controller
        self.requested_target: DeclarationsRouteTargetV1 | None = None

    def populate_navigation(self) -> None:
        table = cast("DataTable[str]", self.query_one("#declarations-navigation", DataTable))
        table.add_column(declarations_copy("tui.declarations.column.destination"), key="destination")
        table.add_column(declarations_copy("tui.declarations.column.availability"), key="availability")
        for destination in _DESTINATION_KEYS:
            state = self.controller.zone_state(_ZONE_BY_DESTINATION[destination])
            table.add_row(
                declarations_copy(_DESTINATION_KEYS[destination]),
                availability_label(state.availability),
                key=destination,
            )

    def handle_navigation(self, event: DataTable.RowSelected) -> bool:
        table = cast("DataTable[str]", event.data_table)
        if table.id != "declarations-navigation":
            return False
        destination = cast("DeclarationsDestinationIdV1", event.row_key.value)
        state = self.controller.zone_state(_ZONE_BY_DESTINATION[destination])
        notice = self.query_one("#declarations-refusal", Static)
        if state.availability not in {
            DeclarationsWorkspaceAvailability.AVAILABLE,
            DeclarationsWorkspaceAvailability.STALE,
        }:
            notice.update(declarations_copy("tui.declarations.refusal.source"))
            return True
        self.requested_target = self.controller.target(destination)
        notice.update("")
        self.post_message(DeclarationsRouteRequested(self.requested_target))
        return True

    def refuse_handoff(self) -> None:
        self.query_one("#declarations-refusal", Static).update(
            declarations_copy("tui.declarations.refusal.handoff")
        )

    def action_back(self) -> None:
        self.dismiss(None)


class DeclarationsRouteRequested(Message):
    """Request that the owning host replace the current internal body."""

    def __init__(self, target: DeclarationsRouteTargetV1) -> None:
        super().__init__()
        self.target = target


__all__ = [
    "DeclarationsWorkspaceController",
    "DeclarationsWorkspaceScreen",
    "DeclarationsRouteRequested",
    "availability_label",
    "declarations_copy",
    "evidence_label",
    "filing_state_label",
    "natural_address",
    "revision_state_label",
    "work_state_label",
]
