"""Closed Declarations route catalogue and injected root factory."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, get_args, override

from textual.app import ComposeResult
from textual.widgets import DataTable, Static

from ....application.modelo.declarations_workspace import (
    DeclarationsWorkspaceAvailability,
    DeclarationsWorkspaceProjectionV1,
    DeclarationsWorkspaceZone,
)
from ....application.operator_actions.catalogue import lookup_action
from ....application.operator_actions.models import ActionReference
from ..components.widgets import ContentDataTable, ContentScroll
from ..navigation import TuiScreenContextV1, TuiScreenFactoryV1
from .controller import DeclarationsWorkspaceController, DeclarationsWorkspaceScreen, declarations_copy
from .filing_history import DeclarationsFilingHistoryScreen
from .models import (
    DeclarationsDestinationIdV1,
    DeclarationsRouteTargetV1,
    FilingHandoffV1,
    ModeloWorkspaceScreenFactoryV1,
    RevisionHandoffV1,
)
from .overview import DeclarationsModeloWorkspaceLauncherScreen, DeclarationsOverviewScreen
from .revisions import DeclarationsRevisionsScreen

type DeclarationsInternalScreenFactoryV1 = Callable[[DeclarationsWorkspaceController], DeclarationsWorkspaceScreen]


class DeclarationsUnavailableScreen(DeclarationsWorkspaceScreen):
    """Explicit refusal without fabricating an empty result."""

    def __init__(self, controller: DeclarationsWorkspaceController, target: DeclarationsRouteTargetV1) -> None:
        """Retain the refused typed target."""
        super().__init__(controller, id="declarations-unavailable-screen")
        self.target = target

    @override
    def compose(self) -> ComposeResult:
        yield Static(declarations_copy("tui.declarations.unavailable.title"), classes="cadrumo-banner", markup=False)
        with ContentScroll(id="declarations-page", classes="cadrumo-scroll declarations-page"):
            yield ContentDataTable[str](id="declarations-navigation", cursor_type="row", zebra_stripes=True)
            yield Static(
                declarations_copy("tui.declarations.refusal.source"),
                id="declarations-refusal",
                classes="declarations-refusal",
                markup=False,
            )

    def on_mount(self) -> None:
        """Populate navigation while preserving the visible refusal."""
        self.populate_navigation()
        self.query_one("#declarations-navigation", DataTable).focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Permit navigation away from the unavailable body."""
        self.handle_navigation(event)


@dataclass(frozen=True, slots=True)
class DeclarationsRouteV1:
    """One route and its projection zone."""
    destination: DeclarationsDestinationIdV1
    zone: DeclarationsWorkspaceZone
    factory: DeclarationsInternalScreenFactoryV1 | None


DECLARATIONS_ROUTES: Final = (
    DeclarationsRouteV1(
        "declarations.overview", DeclarationsWorkspaceZone.DECLARATIONS, DeclarationsOverviewScreen
    ),
    DeclarationsRouteV1(
        "declarations.revisions", DeclarationsWorkspaceZone.CALCULATION_REVISIONS, DeclarationsRevisionsScreen
    ),
    DeclarationsRouteV1(
        "declarations.filing_history", DeclarationsWorkspaceZone.FILING_HISTORY, DeclarationsFilingHistoryScreen
    ),
    DeclarationsRouteV1(
        "declarations.modelo_workspace", DeclarationsWorkspaceZone.DECLARATIONS, None
    ),
)
_ROUTES_BY_ID: Final = {route.destination: route for route in DECLARATIONS_ROUTES}


def declared_declarations_destination_ids() -> frozenset[str]:
    """Return the destination identities from the defining literal."""
    return frozenset(item for item in get_args(DeclarationsDestinationIdV1.__value__) if isinstance(item, str))


if frozenset(_ROUTES_BY_ID) != declared_declarations_destination_ids() or len(_ROUTES_BY_ID) != len(
    DECLARATIONS_ROUTES
):
    raise ValueError("Declarations routes must cover the closed catalogue exactly once")


def resolve_declarations_screen(
    controller: DeclarationsWorkspaceController,
    target: DeclarationsRouteTargetV1,
) -> DeclarationsWorkspaceScreen:
    """Resolve a target without I/O or controller construction."""
    route = _ROUTES_BY_ID[target.destination]
    if target.zone is not route.zone:
        raise ValueError("Declarations route target and zone disagree")
    state = controller.zone_state(route.zone)
    observable = state.availability in {
        DeclarationsWorkspaceAvailability.AVAILABLE,
        DeclarationsWorkspaceAvailability.STALE,
    }
    if not observable or (route.factory is None and controller.modelo_workspace_factory is None):
        return DeclarationsUnavailableScreen(controller, target)
    if route.factory is None:
        return DeclarationsModeloWorkspaceLauncherScreen(controller)
    return route.factory(controller)


def declarations_screen_factory(
    projection: DeclarationsWorkspaceProjectionV1,
    *,
    work_action: ActionReference,
    revisions_action: ActionReference,
    filing_action: ActionReference,
    modelo_workspace_factory: ModeloWorkspaceScreenFactoryV1 | None = None,
    revision_handoff: RevisionHandoffV1 | None = None,
    filing_handoff: FilingHandoffV1 | None = None,
) -> TuiScreenFactoryV1:
    """Bind only injected facts, admissions, and typed handoffs."""
    expected = (
        (work_action, "modelo.work.list"),
        (revisions_action, "modelo.work.revisions"),
        (filing_action, "modelo.filing_record.list"),
    )
    for action, command in expected:
        if lookup_action(action.action_id).target_command_key != command:
            raise ValueError("injected Declarations read action resolves to another application door")

    def create(context: TuiScreenContextV1) -> DeclarationsWorkspaceScreen:
        controller = DeclarationsWorkspaceController(
            context,
            projection,
            work_action=work_action,
            revisions_action=revisions_action,
            filing_action=filing_action,
            modelo_workspace_factory=modelo_workspace_factory,
            revision_handoff=revision_handoff,
            filing_handoff=filing_handoff,
        )
        return resolve_declarations_screen(controller, controller.target("declarations.overview"))

    return create


__all__ = [
    "DECLARATIONS_ROUTES",
    "DeclarationsRouteV1",
    "DeclarationsUnavailableScreen",
    "declarations_screen_factory",
    "resolve_declarations_screen",
]
