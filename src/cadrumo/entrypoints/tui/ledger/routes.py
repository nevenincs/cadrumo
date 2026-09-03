"""Closed internal Ledger route catalogue and injected root factory."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, get_args, override

from textual.app import ComposeResult
from textual.widgets import DataTable, Static

from ....application.ledger.attachment_review import AttachmentReviewItem
from ....application.ledger.workspace import LedgerWorkspaceArea, LedgerWorkspaceProjectionV1
from ....application.operator_actions.catalogue import lookup_action
from ....application.operator_actions.models import ActionReference
from ....core.identity import TransactionId
from ..components.widgets import ContentDataTable, ContentScroll
from ..navigation import TuiScreenContextV1, TuiScreenFactoryV1
from .classification import LedgerClassificationScreen
from .controller import LedgerWorkspaceController, LedgerWorkspaceScreen, ledger_copy
from .entries import LedgerEntriesScreen
from .evidence import LedgerEvidenceScreen
from .import_flow import LedgerImportScreen
from .models import (
    LedgerClassificationSubmitterV1,
    LedgerDestinationIdV1,
    LedgerImportSubmitterV1,
    LedgerLinkSubmitterV1,
    LedgerPreparedImportV1,
    LedgerRouteRefusalV1,
    LedgerRouteTargetV1,
)
from .overview import LedgerOverviewScreen
from .reconciliation import LedgerReconciliationScreen
from .review import LedgerReviewScreen

type LedgerInternalScreenFactoryV1 = Callable[[LedgerWorkspaceController], LedgerWorkspaceScreen]


class LedgerUnavailableScreen(LedgerWorkspaceScreen):
    """Typed placeholder for an unavailable application area or deferred body."""

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
        with ContentScroll(id="ledger-page", classes="cadrumo-scroll ledger-page"):
            yield ContentDataTable[str](id="ledger-navigation", cursor_type="row", zebra_stripes=True)
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
    """One internal destination and its optional implemented read body."""

    destination: LedgerDestinationIdV1
    area: LedgerWorkspaceArea
    factory: LedgerInternalScreenFactoryV1 | None


LEDGER_ROUTES: Final[tuple[LedgerRouteV1, ...]] = (
    LedgerRouteV1("ledger.overview", LedgerWorkspaceArea.OVERVIEW, LedgerOverviewScreen),
    LedgerRouteV1("ledger.entries", LedgerWorkspaceArea.ENTRIES, LedgerEntriesScreen),
    LedgerRouteV1("ledger.review", LedgerWorkspaceArea.REVIEW, LedgerReviewScreen),
    LedgerRouteV1("ledger.import", LedgerWorkspaceArea.IMPORT, LedgerImportScreen),
    LedgerRouteV1("ledger.classification", LedgerWorkspaceArea.CLASSIFICATION, LedgerClassificationScreen),
    LedgerRouteV1("ledger.evidence", LedgerWorkspaceArea.EVIDENCE, LedgerEvidenceScreen),
    LedgerRouteV1("ledger.reconciliation", LedgerWorkspaceArea.RECONCILIATION, LedgerReconciliationScreen),
)
_ROUTES_BY_ID: Final = {route.destination: route for route in LEDGER_ROUTES}


def declared_ledger_destination_ids() -> frozenset[str]:
    """Read the internal closed destination set from its defining type alias."""
    return frozenset(item for item in get_args(LedgerDestinationIdV1.__value__) if isinstance(item, str))


def _require_total_routes() -> None:
    if frozenset(_ROUTES_BY_ID) != declared_ledger_destination_ids() or len(_ROUTES_BY_ID) != len(LEDGER_ROUTES):
        raise ValueError("Ledger routes must cover the internal destination catalogue exactly once")
    if tuple(route.area for route in LEDGER_ROUTES) != tuple(LedgerWorkspaceArea):
        raise ValueError("Ledger routes must preserve canonical workspace area order")


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
    factory = route.factory
    if factory is None:  # pragma: no cover - controller refuses every deferred area
        raise ValueError("Ledger route has no implemented screen")
    return factory(controller)


def ledger_screen_factory(
    projection: LedgerWorkspaceProjectionV1,
    *,
    review_action: ActionReference,
    classify_action: ActionReference | None = None,
    classification_target: TransactionId | None = None,
    classification_submitter: LedgerClassificationSubmitterV1 | None = None,
    prepared_imports: tuple[LedgerPreparedImportV1, ...] = (),
    import_submitter: LedgerImportSubmitterV1 | None = None,
    evidence_action: ActionReference | None = None,
    evidence_items: tuple[AttachmentReviewItem, ...] | None = None,
    link_action: ActionReference | None = None,
    link_submitter: LedgerLinkSubmitterV1 | None = None,
) -> TuiScreenFactoryV1:
    """Bind an injected immutable projection to the outer navigation factory contract."""
    declaration = lookup_action(review_action.action_id)
    if declaration.target_command_key != "ledger.review":
        raise ValueError("injected Ledger review action does not resolve to the canonical review query")
    if classify_action is not None:
        classification_declaration = lookup_action(classify_action.action_id)
        if classification_declaration.target_command_key != "ledger.classify":
            raise ValueError("injected Ledger classification action does not resolve to the canonical command")
    if evidence_action is not None:
        evidence_declaration = lookup_action(evidence_action.action_id)
        if evidence_declaration.target_command_key != "ledger.evidence.review.list":
            raise ValueError("injected Ledger evidence action does not resolve to the canonical review query")
    if link_action is not None:
        link_declaration = lookup_action(link_action.action_id)
        if link_declaration.target_command_key != "ledger.link":
            raise ValueError("injected Ledger link action does not resolve to the canonical command")

    def create(context: TuiScreenContextV1) -> LedgerWorkspaceScreen:
        controller = LedgerWorkspaceController(
            context,
            projection,
            review_action=review_action,
            classify_action=classify_action,
            classification_target=classification_target,
            classification_submitter=classification_submitter,
            prepared_imports=prepared_imports,
            import_submitter=import_submitter,
            evidence_action=evidence_action,
            evidence_items=evidence_items,
            link_action=link_action,
            link_submitter=link_submitter,
        )
        return resolve_ledger_screen(controller, controller.route_target(LedgerWorkspaceArea.OVERVIEW))

    return create


__all__ = [
    "LEDGER_ROUTES",
    "LedgerInternalScreenFactoryV1",
    "LedgerRouteV1",
    "LedgerUnavailableScreen",
    "declared_ledger_destination_ids",
    "ledger_screen_factory",
    "resolve_ledger_screen",
]
