"""The projection-only navigation join for one dedicated TUI session.

The root receives an immutable Home projection refresh door and a closed,
already-admitted destination catalogue.  It mounts one destination at a time,
returns from real child dismissals to refreshed Home, and preserves the Home
row's semantic identity without taking on business, persistence, or network
authority.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, ClassVar, override

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Static

from ...application.overview.home import HomeSessionPosture
from ...application.search.workbench import WorkbenchDestinationAdmissionState
from ...core.i18n.render import tr
from .components.theme import BASE_CSS, install_cadrumo_themes, toggle_appearance, tokenised
from .home import HomeBackRequested, HomeScreen, HomeTarget, HomeTargetSelected
from .navigation import (
    TuiDestinationAdmissionV1,
    TuiDestinationCatalogueV1,
    TuiDestinationRouteV1,
    TuiNavigationTargetV1,
)
from .search import WorkbenchCommandProviderV1, WorkbenchSearchDoorV1, WorkbenchSearchProviderV1

if TYPE_CHECKING:
    from ...application.operations.composition import OperationComposedServices
    from ...application.overview.home import HomeProjectionV1


type HomeRefreshDoorV1 = Callable[[], HomeProjectionV1]
type WorkbenchSearchRefreshDoorV1 = Callable[[], WorkbenchSearchDoorV1]


def _expired_session_catalogue(catalogue: TuiDestinationCatalogueV1) -> TuiDestinationCatalogueV1:
    """Disable every non-Home route in the catalogue after session expiry."""
    routes: list[TuiDestinationRouteV1] = []
    for route in catalogue.routes:
        if route.descriptor.destination == "workbench.home":
            routes.append(route)
            continue
        routes.append(
            TuiDestinationRouteV1(
                descriptor=route.descriptor,
                admission=TuiDestinationAdmissionV1(
                    destination=route.descriptor.destination,
                    state=WorkbenchDestinationAdmissionState.LOCKED,
                    reason_code="session.expired",
                ),
            )
        )
    return TuiDestinationCatalogueV1(routes)


class CadrumoTuiApp(App[None]):
    """Host one composed TUI session and whichever areas are joinable."""

    CSS = tokenised(BASE_CSS)

    BINDINGS: ClassVar = [
        Binding("f3", "toggle_appearance", "", show=False),
        Binding("q", "quit", "", show=False),
    ]
    COMMANDS = App.COMMANDS | {WorkbenchSearchProviderV1, WorkbenchCommandProviderV1}

    def __init__(
        self,
        *,
        services: OperationComposedServices,
        destination_catalogue: TuiDestinationCatalogueV1 | None = None,
        refresh_home: HomeRefreshDoorV1 | None = None,
        workbench_search_service: WorkbenchSearchDoorV1 | None = None,
        refresh_workbench_search: WorkbenchSearchRefreshDoorV1 | None = None,
    ) -> None:
        """Bind the root to the operation services composed for this session."""
        super().__init__()
        self._services = services
        self._destination_catalogue = destination_catalogue
        self._active_destination_catalogue = destination_catalogue
        self._refresh_home = refresh_home
        self._workbench_search_service = workbench_search_service
        self._refresh_workbench_search = refresh_workbench_search
        self._active_target: TuiNavigationTargetV1 | None = None
        self._home_semantic_focus: HomeTarget | None = None

    @property
    def services(self) -> OperationComposedServices:
        """The composed operation services an area receives when it mounts."""
        return self._services

    @property
    def destination_catalogue(self) -> TuiDestinationCatalogueV1:
        """Return the caller-composed closed catalogue for palette navigation."""
        if self._active_destination_catalogue is None:
            raise RuntimeError("the root has no composed destination catalogue")
        return self._active_destination_catalogue

    @property
    def workbench_search_service(self) -> WorkbenchSearchDoorV1:
        """Return the caller-composed application search door for the palette."""
        if self._workbench_search_service is None:
            raise RuntimeError("the root has no composed workbench search service")
        return self._workbench_search_service

    @override
    def compose(self) -> ComposeResult:
        with Vertical(id="root-shell"):
            yield Static(tr("tui.root.title"), id="root-title", markup=False)
            yield Static("", id="root-account", markup=False)
            yield Static(tr("tui.root.no_areas"), id="root-no-areas", markup=False)
        yield Footer()

    def on_mount(self) -> None:
        """Install the shared appearance for this session."""
        install_cadrumo_themes(self)
        if self._destination_catalogue is not None and self._refresh_home is not None:
            self._show_home(None)

    def action_toggle_appearance(self) -> None:
        """Flip between the light and dark appearance."""
        toggle_appearance(self)

    def navigate_to(self, target: TuiNavigationTargetV1, /) -> None:
        """Mount only the current admitted destination with its semantic focus."""
        catalogue = self.destination_catalogue
        if target.destination == "workbench.home":
            self._show_home(self._home_semantic_focus)
            return
        screen = catalogue.create_screen(target)
        self._active_target = target
        self._replace_destination(screen, return_to_home=True)

    def on_home_target_selected(self, event: HomeTargetSelected) -> None:
        """Remember the Home row by its domain identity, never a row position."""
        self._home_semantic_focus = event.target

    def on_home_back_requested(self, _: HomeBackRequested) -> None:
        """Refresh Home after a completed or dismissed journey."""
        if self._refresh_home is not None:
            self._show_home(self._home_semantic_focus)

    def _show_home(self, semantic_focus: HomeTarget | None) -> None:
        """Rebuild Home and restore its actual semantic row after every return."""
        refresh_home = self._refresh_home
        if refresh_home is None:
            return
        projection = refresh_home()
        self.query_one("#root-account", Static).update(projection.account.profile_label or "Account")
        self.query_one("#root-no-areas", Static).display = False
        if self._destination_catalogue is not None:
            self._active_destination_catalogue = (
                _expired_session_catalogue(self._destination_catalogue)
                if projection.account.posture is HomeSessionPosture.EXPIRED
                else self._destination_catalogue
            )
        self._active_target = None
        self._replace_destination(HomeScreen(projection, restore_target=semantic_focus))

    def _on_destination_dismissed(self, _: None) -> None:
        """Return from a real child dismissal through the projection refresh door."""
        self._rebuild_workbench_search()
        self._show_home(self._home_semantic_focus)

    def _rebuild_workbench_search(self) -> None:
        """Replace search only after the owning child has authoritatively returned."""
        refresh_workbench_search = self._refresh_workbench_search
        if refresh_workbench_search is not None:
            self._workbench_search_service = refresh_workbench_search()

    def _replace_destination(self, screen: Screen[None], *, return_to_home: bool = False) -> None:
        """Discard the inactive destination before mounting exactly one replacement."""
        while len(self.screen_stack) > 1:
            self.pop_screen()
        self.push_screen(screen, self._on_destination_dismissed if return_to_home else None)


__all__ = ["CadrumoTuiApp", "HomeRefreshDoorV1", "WorkbenchSearchRefreshDoorV1"]
