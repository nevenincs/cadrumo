"""The projection-only navigation join for one dedicated TUI session.

The root receives an immutable Home projection refresh door and a closed,
already-admitted destination catalogue.  It mounts one destination at a time,
returns from real child dismissals to refreshed Home, and preserves the Home
row's semantic identity without taking on business, persistence, or network
authority.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, ClassVar, cast, override

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ItemGrid, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Static

from ...application.overview.home import HomeSessionPosture
from ...core.i18n.render import tr
from ...core.operations import OperationTerminalCondition
from .account import AccountFactoriesV1, AccountRecomposeReasonV1, AccountRecomposeRequiredV1
from .components.theme import BASE_CSS, install_cadrumo_themes, toggle_appearance, tokenised
from .home import HomeBackRequested, HomeScreen, HomeTarget, HomeTargetSelected
from .navigation import (
    TuiDestinationCatalogueV1,
    TuiFocusIdentityV1,
    TuiNavigationTargetV1,
    TuiScreenContextV1,
)
from .operations.modal import OperationModal, OperationModalOutcomeV1, OperationModalSettledOutcomeV1
from .search import WorkbenchCommandProviderV1, WorkbenchSearchDoorV1, WorkbenchSearchProviderV1

if TYPE_CHECKING:
    from ...application.operations.composition import OperationComposedServices
    from ...application.overview.home import HomeProjectionV1


type HomeRefreshDoorV1 = Callable[[], HomeProjectionV1]
type WorkbenchSearchRefreshDoorV1 = Callable[[], WorkbenchSearchDoorV1]


class CadrumoTuiApp(App[AccountRecomposeRequiredV1 | None]):
    """Host one composed TUI session and whichever areas are joinable."""

    CSS = tokenised(
        BASE_CSS
        + """
    #root-account-bar { width: 100%; height: auto; }
    #root-account { width: 1fr; height: auto; padding: 1 2; text-style: bold; }
    #root-account-actions {
        width: 4fr;
        height: auto;
        grid-gutter: 0 1;
    }
    #root-account-actions Button { width: 1fr; min-width: 0; margin: 0; }
    #root-account-refusal { height: auto; color: $warning; padding: 0 2; }
    """
    )

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
        account_factories: AccountFactoriesV1 | None = None,
    ) -> None:
        """Bind the root to the operation services composed for this session."""
        super().__init__()
        self._services = services
        self._destination_catalogue = destination_catalogue
        self._active_destination_catalogue = destination_catalogue
        self._refresh_home = refresh_home
        self._workbench_search_service = workbench_search_service
        self._refresh_workbench_search = refresh_workbench_search
        self._account_factories = account_factories
        self._workbench_search_refusal_code: str | None = (
            None if workbench_search_service is not None else "workbench.search.unavailable"
        )
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

    @property
    def workbench_search_refusal_code(self) -> str | None:
        """Expose only a sanitized availability code for host presentation."""
        return self._workbench_search_refusal_code

    @override
    def compose(self) -> ComposeResult:
        with Vertical(id="root-shell"):
            yield Static(tr("tui.root.title"), id="root-title", markup=False)
            with Horizontal(id="root-account-bar"):
                yield Static("", id="root-account", markup=False)
                with ItemGrid(id="root-account-actions", min_column_width=12):
                    yield Button(tr("tui.root.account.change_user"), id="root-change-user")
                    yield Button(tr("tui.root.account.password"), id="root-password")
                    yield Button(tr("tui.root.account.profile"), id="root-profile")
                    yield Button(tr("tui.root.account.appearance"), id="root-appearance")
                    yield Button(tr("tui.root.account.language"), id="root-language")
                    yield Button(tr("tui.root.account.sign_out"), id="root-sign-out")
            yield Static("", id="root-account-refusal", markup=False)
            yield Static(tr("tui.root.no_areas"), id="root-no-areas", markup=False)
        yield Footer()

    def on_mount(self) -> None:
        """Install the shared appearance for this session."""
        install_cadrumo_themes(self)
        if self._account_factories is None:
            self._refuse_account_action()
            for button in self.query("#root-account-actions Button"):
                button.disabled = True
        if self._destination_catalogue is not None and self._refresh_home is not None:
            self._show_home(None)

    def action_toggle_appearance(self) -> None:
        """Flip between the light and dark appearance."""
        toggle_appearance(self)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Dispatch account chrome only through the injected existing owners."""
        factories = self._account_factories
        if factories is None:
            self._refuse_account_action()
            return
        match event.button.id:
            case "root-change-user":
                self.push_screen(factories.change_user(), self._on_change_user_dismissed)
            case "root-password":
                self.push_screen(factories.password())
            case "root-profile":
                self.navigate_to(
                    TuiNavigationTargetV1(
                        destination="workbench.profile",
                        focus=TuiFocusIdentityV1(
                            destination="workbench.profile",
                            semantic_key="profile.overview",
                        ),
                    )
                )
            case "root-appearance":
                factories.appearance(cast("App[None]", self))
            case "root-language":
                screen = factories.profile(
                    TuiScreenContextV1(destination="workbench.profile")
                )
                self._replace_destination(screen, return_to_home=True)
                self.call_after_refresh(factories.language, screen)
            case "root-sign-out":
                self.run_worker(self._open_sign_out(), name="account-sign-out", exclusive=True)
            case _:
                return

    def _on_change_user_dismissed(self, outcome: object | None) -> None:
        """Accept only the real Login owner's non-secret authenticated result."""
        from ...application.user_profile.login_session import ProfileLoginOutcome

        if not isinstance(outcome, ProfileLoginOutcome):
            return
        self._request_recompose(
            AccountRecomposeRequiredV1(
                reason=AccountRecomposeReasonV1.CHANGE_USER,
                profile_id=str(outcome.bucket_id),
                profile_label=outcome.label,
            )
        )

    async def _open_sign_out(self) -> None:
        """Submit strong close and hand observation to the canonical modal."""
        factories = self._account_factories
        if factories is None:
            self._refuse_account_action()
            return
        try:
            controller = await factories.sign_out()
        except Exception:
            self._refuse_account_action()
            return
        self.push_screen(OperationModal(controller), self._on_sign_out_dismissed)

    def _on_sign_out_dismissed(self, outcome: OperationModalOutcomeV1 | None) -> None:
        """Rebootstrap only after the canonical operation reports success."""
        if (
            isinstance(outcome, OperationModalSettledOutcomeV1)
            and outcome.view_model.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
        ):
            self._request_recompose(
                AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.SIGNED_OUT)
            )
            return
        if outcome is not None:
            self._refuse_account_action()

    def _refuse_account_action(self) -> None:
        """Expose one localized fail-closed message without exception details."""
        if self.is_mounted():
            self.query_one("#root-account-refusal", Static).update(tr("tui.root.account.unavailable"))

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
        self.query_one("#root-account", Static).update(
            projection.account.profile_label or tr("tui.root.account.default_profile")
        )
        self.query_one("#root-no-areas", Static).display = False
        if projection.account.posture is HomeSessionPosture.EXPIRED:
            self._request_recompose(AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.EXPIRED))
            return
        if self._destination_catalogue is not None:
            self._active_destination_catalogue = self._destination_catalogue
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
            try:
                refreshed = refresh_workbench_search()
            except Exception:  # projection failures must not leak protected diagnostics
                self._workbench_search_refusal_code = "workbench.search.refresh_unavailable"
                return
            self._workbench_search_service = refreshed
            self._workbench_search_refusal_code = None

    def _replace_destination(self, screen: Screen[None], *, return_to_home: bool = False) -> None:
        """Discard the inactive destination before mounting exactly one replacement."""
        while len(self.screen_stack) > 1:
            self.pop_screen()
        self.push_screen(screen, self._on_destination_dismissed if return_to_home else None)

    def _request_recompose(self, outcome: AccountRecomposeRequiredV1) -> None:
        """Sever every profile-bound capability before returning to bootstrap."""
        self._account_factories = None
        self._destination_catalogue = None
        self._active_destination_catalogue = None
        self._refresh_home = None
        self._workbench_search_service = None
        self._refresh_workbench_search = None
        self._active_target = None
        self._home_semantic_focus = None
        self.exit(outcome)


__all__ = ["CadrumoTuiApp", "HomeRefreshDoorV1", "WorkbenchSearchRefreshDoorV1"]
