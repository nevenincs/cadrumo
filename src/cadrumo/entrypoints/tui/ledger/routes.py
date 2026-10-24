"""Closed internal Ledger route catalogue and injected root factory."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, override

from textual.app import ComposeResult
from textual.widgets import DataTable, Static

from ....application.ledger.attachment_review import AttachmentReviewItem
from ....application.ledger.workspace import LedgerWorkspaceArea, LedgerWorkspaceProjectionV1
from ....application.operator_actions.models import ActionReference
from ....core.i18n.render import tr
from ..components.language import localized
from ..destination_alias import closed_destination_ids
from ..navigation import TuiScreenContextV1, TuiScreenFactoryV1
from .actividad_asset import ActivityAssetTuiActionsV1
from .classification import LedgerClassificationScreen
from .controller import LEDGER_TRANSACTION_FOCUS, LedgerWorkspaceController, LedgerWorkspaceScreen
from .entries import LedgerEntriesScreen
from .evidence import LedgerEvidenceReviewListDoorV1, LedgerEvidenceScreen
from .import_flow import LedgerImportScreen
from .models import (
    LEDGER_DESTINATION_BY_AREA,
    LedgerClassificationPatchBuilderV1,
    LedgerClassificationSubmitterV1,
    LedgerDestinationIdV1,
    LedgerEvidenceDoorV1,
    LedgerExclusionSubmitterV1,
    LedgerImportDoorV1,
    LedgerInvoiceAddDoorV1,
    LedgerLinkSubmitterV1,
    LedgerRecordDoorsV1,
    LedgerRouteRefusalV1,
    LedgerRouteTargetV1,
)
from .overview import LedgerOverviewScreen
from .own_accounts import LedgerOwnAccountDoorV1
from .reconciliation import LedgerReconciliationScreen
from .review import LedgerReviewDoorV1, LedgerReviewScreen
from .tools import LedgerToolV1
from .workspace_injection import LedgerWorkspaceInjection, LedgerWorkspaceRefreshDoorV1
from .workspace_presentation import ledger_workspace_page

type LedgerInternalScreenFactoryV1 = Callable[[LedgerWorkspaceController], LedgerWorkspaceScreen]


class LedgerUnavailableScreen(LedgerWorkspaceScreen):
    """Typed placeholder for an area unavailable in application state."""

    def __init__(
        self,
        controller: LedgerWorkspaceController,
        refusal: LedgerRouteRefusalV1,
        *,
        selection_dropped: bool = False,
    ) -> None:
        """Retain the typed refusal without resolving its protected reason code.

        ``selection_dropped`` says the page opened with one transaction selected
        and shows no entry at all, so it says that beside the refusal.
        """
        super().__init__(controller, id="ledger-unavailable-screen")
        self.refusal = refusal
        self._route_refusal = refusal
        self._selection_dropped = selection_dropped

    @override
    def compose(self) -> ComposeResult:
        """Render the explicit unavailability and no action affordance."""
        yield localized(
            Static(
                tr("tui.ledger.unavailable.title"),
                classes="cadrumo-banner",
            ),
            "tui.ledger.unavailable.title",
        )
        with ledger_workspace_page() as navigation:
            yield navigation
            yield localized(
                Static(
                    tr(self._route_refusal.reason_key),
                    id="ledger-refusal",
                    classes="ledger-refusal",
                    markup=False,
                ),
                self._route_refusal.reason_key,
            )
            if self._selection_dropped:
                yield localized(
                    Static(
                        tr("tui.ledger.unavailable.selection_dropped"),
                        id="ledger-selection-dropped",
                        classes="ledger-refusal",
                        markup=False,
                    ),
                    "tui.ledger.unavailable.selection_dropped",
                )

    def on_mount(self) -> None:
        """Keep the entire workspace vocabulary reachable beside the refusal."""
        self.populate_navigation()
        self.query_one("#ledger-navigation", DataTable).focus()


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
    if frozenset(_ROUTES_BY_ID) != closed_destination_ids(LedgerDestinationIdV1) or len(_ROUTES_BY_ID) != len(
        LEDGER_ROUTES
    ):
        raise ValueError("Ledger routes must cover the internal destination catalogue exactly once")
    if tuple(route.area for route in LEDGER_ROUTES) != tuple(LedgerWorkspaceArea):
        raise ValueError("Ledger routes must preserve canonical workspace area order")
    if frozenset(_SCREEN_BY_AREA) != frozenset(LedgerWorkspaceArea):
        raise ValueError("Ledger routes must name a read body for every workspace area")


_require_total_routes()


def resolve_ledger_screen(
    controller: LedgerWorkspaceController,
    target: LedgerRouteTargetV1,
    *,
    selection_dropped: bool = False,
) -> LedgerWorkspaceScreen:
    """Resolve one internal route without reading state or invoking an action.

    ``selection_dropped`` is carried only to the unavailable page, the one
    screen that shows no entry whatever was selected.
    """
    route = _ROUTES_BY_ID[target.destination]
    if route.area is not target.area:
        raise ValueError("Ledger target destination and area disagree")
    refusal = controller.refusal_for(route.area)
    if refusal is not None:
        return LedgerUnavailableScreen(controller, refusal, selection_dropped=selection_dropped)
    return route.factory(controller)


def ledger_screen_factory(
    projection: LedgerWorkspaceProjectionV1,
    *,
    review_action: ActionReference,
    review_door: LedgerReviewDoorV1 | None = None,
    classify_action: ActionReference | None = None,
    classification_submitter: LedgerClassificationSubmitterV1 | None = None,
    classification_patch_builder: LedgerClassificationPatchBuilderV1 | None = None,
    import_door: LedgerImportDoorV1 | None = None,
    evidence_action: ActionReference | None = None,
    evidence_items: tuple[AttachmentReviewItem, ...] | None = None,
    evidence_review_door: LedgerEvidenceReviewListDoorV1 | None = None,
    link_action: ActionReference | None = None,
    link_submitter: LedgerLinkSubmitterV1 | None = None,
    invoice_add_door: LedgerInvoiceAddDoorV1 | None = None,
    exclusion_submitter: LedgerExclusionSubmitterV1 | None = None,
    evidence_door: LedgerEvidenceDoorV1 | None = None,
    refresh: LedgerWorkspaceRefreshDoorV1 | None = None,
    activity_asset_actions: ActivityAssetTuiActionsV1 | None = None,
    record_doors: LedgerRecordDoorsV1 | None = None,
    own_account_door: LedgerOwnAccountDoorV1 | None = None,
    tools: tuple[LedgerToolV1, ...] = (),
) -> TuiScreenFactoryV1:
    """Bind an injected immutable projection to the outer navigation factory contract."""
    injection = LedgerWorkspaceInjection(
        review_action=review_action,
        review_door=review_door,
        classify_action=classify_action,
        classification_submitter=classification_submitter,
        classification_patch_builder=classification_patch_builder,
        import_door=import_door,
        evidence_action=evidence_action,
        evidence_items=evidence_items,
        evidence_review_door=evidence_review_door,
        link_action=link_action,
        link_submitter=link_submitter,
        invoice_add_door=invoice_add_door,
        exclusion_submitter=exclusion_submitter,
        evidence_door=evidence_door,
        refresh=refresh,
        activity_asset_actions=activity_asset_actions,
        record_doors=record_doors,
        own_account_door=own_account_door,
        tools=tools,
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
        # A Ledger opened on one transaction, as a link selecting it asks, lands
        # on the entries where that transaction is selected.
        selects_transaction = context.focus is not None and context.focus.semantic_key == LEDGER_TRANSACTION_FOCUS
        landing = LedgerWorkspaceArea.ENTRIES if selects_transaction else LedgerWorkspaceArea.OVERVIEW
        area = area_by_action.get(context.action_candidate_id or "", landing)
        if controller.refusal_for(area) is not None:
            # The overview shows no entry, so a selection is dropped there and
            # the page says so. Only the entries were asked for by the
            # selection; another area picked by an action is not the selection's
            # landing, and the overview's notice names the entries.
            if (
                selects_transaction
                and area is LedgerWorkspaceArea.ENTRIES
                and controller.refusal_for(LedgerWorkspaceArea.OVERVIEW) is None
            ):
                return LedgerOverviewScreen(controller, selection_dropped=True)
            area = LedgerWorkspaceArea.OVERVIEW
        return resolve_ledger_screen(controller, controller.route_target(area), selection_dropped=selects_transaction)

    return create


__all__ = [
    "LEDGER_ROUTES",
    "LedgerInternalScreenFactoryV1",
    "LedgerRouteV1",
    "LedgerUnavailableScreen",
    "ledger_screen_factory",
    "resolve_ledger_screen",
]
