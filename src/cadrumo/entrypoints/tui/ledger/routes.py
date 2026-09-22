"""Closed internal Ledger route catalogue and injected root factory."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, override

from textual.app import ComposeResult
from textual.widgets import DataTable, Static

from ....application.actividad_asset.operations import ActivityAssetOperations
from ....application.ledger.attachment_review import AttachmentReviewItem
from ....application.ledger.workspace import LedgerWorkspaceArea, LedgerWorkspaceProjectionV1
from ....application.operator_actions.models import ActionReference
from ..navigation import TuiScreenContextV1, TuiScreenFactoryV1
from .actividad_asset import ActivityAssetTuiActionsV1
from .classification import LedgerClassificationScreen
from .controller import LedgerWorkspaceController, LedgerWorkspaceScreen, ledger_copy
from .entries import LedgerEntriesScreen
from .evidence import LedgerEvidenceScreen
from .import_flow import LedgerImportScreen
from .models import (
    LEDGER_DESTINATION_BY_AREA,
    LedgerClassificationSubmitterV1,
    LedgerDestinationIdV1,
    LedgerEvidenceDoorV1,
    LedgerExclusionSubmitterV1,
    LedgerImportDoorV1,
    LedgerInvoiceAddDoorV1,
    LedgerLinkSubmitterV1,
    LedgerRouteRefusalV1,
    LedgerRouteTargetV1,
    declared_ledger_destination_ids,
)
from .overview import LedgerOverviewScreen
from .reconciliation import LedgerReconciliationScreen
from .record_doors import LedgerRecordDoors
from .review import LedgerReviewScreen
from .workspace_injection import LedgerWorkspaceInjection, LedgerWorkspaceRefreshDoorV1
from .workspace_presentation import ledger_workspace_page

type LedgerInternalScreenFactoryV1 = Callable[[LedgerWorkspaceController], LedgerWorkspaceScreen]


def actividad_asset_tui_actions(*, operations: ActivityAssetOperations) -> ActivityAssetTuiActionsV1:
    """Compose the activity-asset TUI door from the same application operations as CLI."""
    return ActivityAssetTuiActionsV1(operations=operations)


class LedgerUnavailableScreen(LedgerWorkspaceScreen):
    """Typed placeholder for an area unavailable in application state."""

    def __init__(self, controller: LedgerWorkspaceController, refusal: LedgerRouteRefusalV1) -> None:
        """Retain the typed refusal without resolving its protected reason code."""
        super().__init__(controller, id="ledger-unavailable-screen")
        self.refusal = refusal
        self._route_refusal = refusal

    @override
    def compose(self) -> ComposeResult:
        """Render the explicit unavailability and no action affordance."""
        yield Static(
            ledger_copy("tui.ledger.unavailable.title"),
            classes="cadrumo-banner",
        )
        with ledger_workspace_page() as navigation:
            yield navigation
            yield Static(
                ledger_copy(self._route_refusal.reason_key),
                id="ledger-refusal",
                classes="ledger-refusal",
                markup=False,
            )

    def on_mount(self) -> None:
        """Keep the entire workspace vocabulary reachable beside the refusal."""
        self.populate_navigation()
        self.query_one("#ledger-navigation", DataTable).focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Allow movement away from a placeholder while preserving refusals."""
        self.handle_navigation_selection(event)


@dataclass(frozen=True, slots=True)
class LedgerRouteV1:
    """One internal destination and its read body."""

    destination: LedgerDestinationIdV1
    area: LedgerWorkspaceArea
    factory: LedgerInternalScreenFactoryV1


#: Which read body each area opens. Only the screens are declared here; the
#: destination each area resolves to comes from the canonical pairing, so this
#: catalogue cannot disagree with the controller about where an area leads.
_SCREEN_BY_AREA: Final[dict[LedgerWorkspaceArea, LedgerInternalScreenFactoryV1]] = {
    LedgerWorkspaceArea.OVERVIEW: LedgerOverviewScreen,
    LedgerWorkspaceArea.ENTRIES: LedgerEntriesScreen,
    LedgerWorkspaceArea.REVIEW: LedgerReviewScreen,
    LedgerWorkspaceArea.IMPORT: LedgerImportScreen,
    LedgerWorkspaceArea.CLASSIFICATION: LedgerClassificationScreen,
    LedgerWorkspaceArea.EVIDENCE: LedgerEvidenceScreen,
    LedgerWorkspaceArea.RECONCILIATION: LedgerReconciliationScreen,
}

LEDGER_ROUTES: Final[tuple[LedgerRouteV1, ...]] = tuple(
    LedgerRouteV1(destination, area, _SCREEN_BY_AREA[area]) for area, destination in LEDGER_DESTINATION_BY_AREA.items()
)
_ROUTES_BY_ID: Final = {route.destination: route for route in LEDGER_ROUTES}


def _require_total_routes() -> None:
    """Refuse at import unless every area has a body and a distinct destination.

    The destination half is settled by the pairing this builds from, so what
    is left to check here is the screen half: an area absent from
    ``_SCREEN_BY_AREA`` yields a route with no factory, which reaches the
    operator as a raise rather than a typed refusal.
    """
    if frozenset(_ROUTES_BY_ID) != declared_ledger_destination_ids() or len(_ROUTES_BY_ID) != len(LEDGER_ROUTES):
        raise ValueError("Ledger routes must cover the internal destination catalogue exactly once")
    if tuple(route.area for route in LEDGER_ROUTES) != tuple(LedgerWorkspaceArea):
        raise ValueError("Ledger routes must preserve canonical workspace area order")
    if frozenset(_SCREEN_BY_AREA) != frozenset(LedgerWorkspaceArea):
        raise ValueError("Ledger routes must name a read body for every workspace area")


_require_total_routes()


def resolve_ledger_screen(
    controller: LedgerWorkspaceController,
    target: LedgerRouteTargetV1,
) -> LedgerWorkspaceScreen:
    """Resolve one internal route without reading state or invoking an action."""
    route = _ROUTES_BY_ID[target.destination]
    if route.area is not target.area:
        raise ValueError("Ledger target destination and area disagree")
    refusal = controller.refusal_for(route.area)
    if refusal is not None:
        return LedgerUnavailableScreen(controller, refusal)
    return route.factory(controller)


def ledger_screen_factory(
    projection: LedgerWorkspaceProjectionV1,
    *,
    review_action: ActionReference,
    classify_action: ActionReference | None = None,
    classification_submitter: LedgerClassificationSubmitterV1 | None = None,
    import_door: LedgerImportDoorV1 | None = None,
    evidence_action: ActionReference | None = None,
    evidence_items: tuple[AttachmentReviewItem, ...] | None = None,
    link_action: ActionReference | None = None,
    link_submitter: LedgerLinkSubmitterV1 | None = None,
    invoice_add_door: LedgerInvoiceAddDoorV1 | None = None,
    exclusion_submitter: LedgerExclusionSubmitterV1 | None = None,
    evidence_door: LedgerEvidenceDoorV1 | None = None,
    refresh: LedgerWorkspaceRefreshDoorV1 | None = None,
    activity_asset_actions: ActivityAssetTuiActionsV1 | None = None,
    record_doors: LedgerRecordDoors | None = None,
) -> TuiScreenFactoryV1:
    """Bind an injected immutable projection to the outer navigation factory contract."""
    injection = LedgerWorkspaceInjection(
        review_action=review_action,
        classify_action=classify_action,
        classification_submitter=classification_submitter,
        import_door=import_door,
        evidence_action=evidence_action,
        evidence_items=evidence_items,
        link_action=link_action,
        link_submitter=link_submitter,
        invoice_add_door=invoice_add_door,
        exclusion_submitter=exclusion_submitter,
        evidence_door=evidence_door,
        refresh=refresh,
        activity_asset_actions=activity_asset_actions,
        record_doors=record_doors,
    )

    # Which area performs each injected action. Classification needs an entry
    # chosen first, so a request to classify opens the entries to choose from.
    area_by_action = {
        str(action.action_id): area
        for action, area in (
            (review_action, LedgerWorkspaceArea.REVIEW),
            (classify_action, LedgerWorkspaceArea.ENTRIES),
            (evidence_action, LedgerWorkspaceArea.EVIDENCE),
            (link_action, LedgerWorkspaceArea.RECONCILIATION),
        )
        if action is not None
    }

    def create(context: TuiScreenContextV1) -> LedgerWorkspaceScreen:
        controller = LedgerWorkspaceController(context, projection, injection)
        area = area_by_action.get(context.action_candidate_id or "", LedgerWorkspaceArea.OVERVIEW)
        if controller.refusal_for(area) is not None:
            area = LedgerWorkspaceArea.OVERVIEW
        return resolve_ledger_screen(controller, controller.route_target(area))

    return create


__all__ = [
    "LEDGER_ROUTES",
    "LedgerInternalScreenFactoryV1",
    "LedgerRouteV1",
    "LedgerUnavailableScreen",
    "actividad_asset_tui_actions",
    "ledger_screen_factory",
    "resolve_ledger_screen",
]
