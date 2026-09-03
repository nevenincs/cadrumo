"""The root navigation join for one dedicated TUI session.

An area is mounted here only once it exposes a host-agnostic screen and its
cohort is green. BOTH CONDITIONS NOW HOLD FOR EVERY AREA, and this docstring
previously said otherwise -- it recorded that profile, secret and flow expose
a Textual application rather than a mountable screen, and that Modelo was held
back by its own cohort gate. Neither is true any more: every area exposes
Screen subclasses, and the application forms that remain are launch wrappers
over those screens for callers arriving from the command line, not the areas'
shape. A caller that already has a running application mounts the screen.

What is still missing is not a precondition but a DESIGN: this root has no
navigation model. Mounting one area would make it the whole product, and
mounting several without a way to move between them offers destinations an
operator cannot reach. So it mounts no area and says so on screen, rather
than composing a join that has not been decided.

The session's composed operation services are held here so that an area
receives them at mount time without reaching for a global; nothing in this
module constructs them, and nothing here wires a concrete adapter.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, ClassVar, override

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Static

from ...core.i18n.render import tr
from .components.theme import BASE_CSS, install_cadrumo_themes, toggle_appearance, tokenised
from .home import HomeBackRequested, HomeScreen
from .navigation import TuiDestinationCatalogueV1, TuiFocusIdentityV1, TuiNavigationTargetV1
from .search import WorkbenchCommandProviderV1, WorkbenchSearchDoorV1, WorkbenchSearchProviderV1

if TYPE_CHECKING:
    from ...application.operations.composition import OperationComposedServices
    from ...application.overview.home import HomeProjectionV1


type HomeRefreshDoorV1 = Callable[[], HomeProjectionV1]


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
    ) -> None:
        """Bind the root to the operation services composed for this session."""
        super().__init__()
        self._services = services
        self._destination_catalogue = destination_catalogue
        self._refresh_home = refresh_home
        self._workbench_search_service = workbench_search_service
        self._active_target: TuiNavigationTargetV1 | None = None

    @property
    def services(self) -> OperationComposedServices:
        """The composed operation services an area receives when it mounts."""
        return self._services

    @property
    def destination_catalogue(self) -> TuiDestinationCatalogueV1:
        """Return the caller-composed closed catalogue for palette navigation."""
        if self._destination_catalogue is None:
            raise RuntimeError("the root has no composed destination catalogue")
        return self._destination_catalogue

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
            self.navigate_to(
                TuiNavigationTargetV1(
                    destination="workbench.home",
                    focus=TuiFocusIdentityV1(destination="workbench.home", semantic_key="navigation.home"),
                )
            )

    def action_toggle_appearance(self) -> None:
        """Flip between the light and dark appearance."""
        toggle_appearance(self)

    def navigate_to(self, target: TuiNavigationTargetV1, /) -> None:
        """Mount only the current admitted destination with its semantic focus."""
        catalogue = self.destination_catalogue
        if target.destination == "workbench.home":
            self._show_home(target.focus)
            return
        self._active_target = target
        self._replace_destination(catalogue.create_screen(target))

    def on_home_back_requested(self, _: HomeBackRequested) -> None:
        """Refresh Home after a completed or dismissed journey."""
        if self._refresh_home is not None:
            self._show_home(None)

    def _show_home(self, focus: TuiFocusIdentityV1 | None) -> None:
        """Rebuild the projection-only Home screen after every return."""
        refresh_home = self._refresh_home
        if refresh_home is None:
            return
        projection = refresh_home()
        self.query_one("#root-account", Static).update(projection.account.profile_label or "Account")
        self.query_one("#root-no-areas", Static).display = False
        if projection.account.posture.value == "expired":
            self._active_target = None
            self._replace_destination(HomeScreen(projection))
            return
        self._active_target = None
        self._replace_destination(HomeScreen(projection))

    def _replace_destination(self, screen: Screen[None]) -> None:
        """Discard the inactive destination before mounting exactly one replacement."""
        while len(self.screen_stack) > 1:
            self.pop_screen()
        self.push_screen(screen)


__all__ = ["CadrumoTuiApp", "HomeRefreshDoorV1"]
