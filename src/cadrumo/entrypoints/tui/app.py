"""The projection-only navigation join for one dedicated TUI session.

The root receives an immutable Home projection refresh door and a closed,
already-admitted destination catalogue.  It mounts one destination at a time,
returns from real child dismissals to refreshed Home, and preserves the Home
row's semantic identity without taking on business, persistence, or network
authority.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, ClassVar, Final, override

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Static

from ...application.overview.home import HomeSessionPosture
from ...core.async_cleanup import await_cancellation_complete
from ...core.diagnostic_log import diagnostic_error_fields, diagnostic_event
from ...core.errors.hierarchy import InternalInvariantError
from ...core.i18n.render import tr
from ...core.logging import get_logger
from ...core.startup_phase_log import log_startup_phase
from .account import (
    AccountFactoriesV1,
    AccountRecomposeReasonV1,
    AccountRecomposeRequiredV1,
    AccountSessionExpiredError,
    AccountSessionReaderV1,
    RuntimeUpgradePending,
    WorkbenchAccountProviderV1,
)
from .account_action_app import ACCOUNT_KEYS, AccountActionApp
from .app_navigation import RootNavigationMixin
from .components.account_chrome import (
    AccountActionV1,
    AccountBar,
)
from .components.theme import BASE_CSS, install_cadrumo_themes, tokenised
from .home import (
    HomeBackRequested,
    HomeLinkSelected,
    HomeScreen,
    HomeTarget,
    HomeTargetSelected,
)
from .navigation import (
    TuiDestinationCatalogueV1,
    TuiNavigationTargetV1,
)
from .operations.palette import WorkbenchOperationProviderV1
from .presentation import PagePresentationRequested, presentation_target
from .root_binding import (
    DestinationCatalogueRefreshDoorV1,
    HomeRefreshDoorV1,
    RootBindingV1,
    RootLoaderV1,
    RootPresentationV1,
    WorkbenchSearchRefreshDoorV1,
)
from .search import WorkbenchCommandProviderV1, WorkbenchSearchDoorV1, WorkbenchSearchProviderV1

if TYPE_CHECKING:
    from textual.timer import Timer
    from textual.worker import Worker

    from cadrumo_client.contracts.navigation import ViewLink

    from ...application.overview.home import HomeAccountSession, HomeProjectionV1
    from .secret.passphrase import PassphraseScreen


_SESSION_WATCH_SECONDS: Final = 30.0
"""How often the root checks whether the session has lapsed when no retirement is pushed to it."""


class CadrumoTuiApp(RootNavigationMixin, AccountActionApp):
    """Host one composed TUI session and whichever areas are joinable."""

    _active_destination_catalogue: TuiDestinationCatalogueV1 | None
    _workbench_search_service: WorkbenchSearchDoorV1 | None
    DEFER_TERMINAL_READY = True

    CSS = tokenised(
        BASE_CSS
        + """
    #root-updating { display: none; padding: $cadrumo-space-0 $cadrumo-gutter; }
    #root-retry { display: none; margin: 0 $cadrumo-gutter; }
    #root-account-refusal, #root-navigation-refusal, #root-read-refusal {
        height: auto;
        color: $warning;
        padding: $cadrumo-space-0 $cadrumo-gutter;
    }
    """
    )

    BINDINGS: ClassVar = [
        # Descriptions are written per render by :meth:`_describe_account_keys`,
        # not here: a class body resolves once at import, in whichever language
        # the process started in.
        *(
            Binding(
                key, "toggle_appearance" if action is AccountActionV1.APPEARANCE else f"account('{action.value}')", ""
            )
            for key, action in ACCOUNT_KEYS.items()
        ),
        Binding("q", "quit", "", show=False),
    ]
    COMMANDS = App.COMMANDS | {
        WorkbenchSearchProviderV1,
        WorkbenchCommandProviderV1,
        WorkbenchOperationProviderV1,
        WorkbenchAccountProviderV1,
    }

    def __init__(
        self,
        *,
        destination_catalogue: TuiDestinationCatalogueV1 | None = None,
        refresh_home: HomeRefreshDoorV1 | None = None,
        workbench_search_service: WorkbenchSearchDoorV1 | None = None,
        refresh_workbench_search: WorkbenchSearchRefreshDoorV1 | None = None,
        refresh_destination_catalogue: DestinationCatalogueRefreshDoorV1 | None = None,
        account_factories: AccountFactoriesV1 | None = None,
        read_account_session: AccountSessionReaderV1 | None = None,
        note_activity: Callable[[], Awaitable[None]] | None = None,
        load_root: RootLoaderV1 | None = None,
    ) -> None:
        """Bind the shell to caller-owned doors.

        ``load_root`` replaces the individual doors. The shell renders first,
        and a worker thread builds the first generation so opening the
        workbench never freezes the terminal.
        """
        super().__init__()
        self._startup_started = time.monotonic()
        self._startup_ready = False
        self._destination_catalogue = destination_catalogue
        self._active_destination_catalogue = destination_catalogue
        self._refresh_home = refresh_home
        self._workbench_search_service = workbench_search_service
        self._refresh_workbench_search = refresh_workbench_search
        self._returning_home = False
        """Whether a return to Home is re-reading the generation off the event loop."""
        self._home_rebuilding = False
        """Whether a Home rebuild is reading its projection off the event loop."""
        self._home_request: HomeTarget | None = None
        """The row the next rebuilt Home restores; the latest request wins."""
        self._navigation_revision = 0
        self._home_navigation_revision = 0
        self._swap_revision: int | None = None
        """The navigation whose destination swap is requested and has not yet removed the old screens."""
        self._load_root = load_root
        """Builds the workbench root off the event loop once the shell has rendered."""
        self._refresh_destination_catalogue = refresh_destination_catalogue
        self._account_factories = account_factories
        self._unsubscribe_retirement: Callable[[], None] | None = None
        self._session_lapse_timer: Timer | None = None
        """Fires at the known expiry when retirement is pushed; nothing polls meanwhile."""
        self._unsubscribe_notices: Callable[[], None] | None = None
        self._unsubscribe_language: Callable[[], None] | None = None
        self._unsubscribe_presentation: Callable[[], None] | None = None
        self._language_pending = False
        self._language_refreshing = False
        self._language_revision = 0
        self._language_epoch = 0
        self._language_retry_attempt = 0
        self._language_retry_timer: Timer | None = None
        self._language_worker: Worker[None] | None = None
        self._language_pending_screens: set[Screen[object]] = set()

        self._home_refresh_refusal_code: str | None = None
        """Why the last Home refresh was refused, or ``None`` when it succeeded."""
        self._workbench_search_refusal_code: str | None = (
            None if workbench_search_service is not None else "workbench.search.unavailable"
        )
        self._active_target: TuiNavigationTargetV1 | None = None
        self._home_semantic_focus: HomeTarget | None = None
        self._account_session: HomeAccountSession | None = None
        self._onboarding_offered = False
        """Whether this session has already opened the setup walk once."""
        self._initial_destination: TuiNavigationTargetV1 | None = None
        self._read_account_session = read_account_session
        self._note_activity = note_activity
        self._last_activity_sent: float | None = None
        self._activity_pending = False
        self._account_session_polling = False
        """Checks the live session's deadline without touching it, or ``None``.

        Kept apart from the Home refresh on purpose: that refresh opens secure
        objects, and every open rolls the idle deadline forward, so a timer
        that refreshed Home would keep an idle session alive forever."""
        self._password_screen: PassphraseScreen | None = None
        self._recomposition_pending = False

    @property
    def destination_catalogue(self) -> TuiDestinationCatalogueV1:
        """Return the caller-composed closed catalogue for palette navigation."""
        if self._active_destination_catalogue is None:
            raise InternalInvariantError("the root has no composed destination catalogue")
        return self._active_destination_catalogue

    def _record_initial_screen_ready(self, screen: Screen[None]) -> None:
        """Time the first rendered destination without recording profile data."""
        if self._startup_ready or self._recomposition_pending or self.screen is not screen:
            return
        self._startup_ready = True
        self.present_terminal()
        log_startup_phase(
            get_logger(__name__), "tui_initial_screen_ready", "leave", time.monotonic() - self._startup_started
        )

    @property
    def workbench_search_service(self) -> WorkbenchSearchDoorV1:
        """Return the caller-composed application search door for the palette."""
        if self._workbench_search_service is None:
            raise InternalInvariantError("the root has no composed workbench search service")
        return self._workbench_search_service

    @property
    def workbench_search_refusal_code(self) -> str | None:
        """Expose only a sanitized availability code for host presentation."""
        return self._workbench_search_refusal_code

    @override
    def compose(self) -> ComposeResult:
        with Vertical(id="root-shell"):
            yield Static(tr("tui.root.title"), id="root-title", markup=False)
            yield AccountBar(id="root-account-bar")
            yield Static("", id="root-account-refusal", markup=False)
            yield Static("", id="root-navigation-refusal", markup=False)
            yield Static("", id="root-read-refusal", markup=False)
            yield Button(tr("tui.root.retry"), id="root-retry")
            yield Static(tr("tui.root.no_areas"), id="root-no-areas", markup=False)
            yield Static(tr("tui.root.updating"), id="root-updating", markup=False)
        yield Footer(compact=True)

    def on_mount(self) -> None:
        """Install the shared appearance for this session."""
        install_cadrumo_themes(self)
        if self._load_root is not None:
            opening = self.query_one("#root-updating", Static)
            opening.update(tr("tui.root.opening"))
            opening.display = True
            self.run_worker(self._open_root(self._load_root), group="root-open")
            return
        self._start_session()

    async def _open_root(self, load_root: RootLoaderV1) -> None:
        """Build the workbench root on a worker thread, then bind it on the loop."""
        self.query_one("#root-no-areas", Static).display = False
        self.query_one("#root-updating", Static).display = True
        try:
            binding = await await_cancellation_complete(asyncio.to_thread(load_root), task_name="tui-root-load")
        except AccountSessionExpiredError as error:
            if self._load_root is load_root and self.is_running:
                self._request_recompose(AccountRecomposeRequiredV1(reason=self._session_failure_reason(error)))
            return
        except Exception as error:
            diagnostic_event(
                get_logger(__name__),
                "tui_root_open_failed",
                fields=diagnostic_error_fields(error),
                primary_error=error,
            )
            if self._load_root is load_root and self.is_running:
                self._home_refresh_refusal_code = "workbench.home.refresh_unavailable"
                self.query_one("#root-updating", Static).display = False
                self._offer_root_retry()
            return
        if self._load_root is not load_root or not self.is_running:
            return
        self._bind_root(binding)
        opening = self.query_one("#root-updating", Static)
        opening.display = False
        opening.update(tr("tui.root.updating"))
        self._start_session()

    def _bind_root(self, binding: RootBindingV1) -> None:
        self._destination_catalogue = binding.destination_catalogue
        self._active_destination_catalogue = binding.destination_catalogue
        self._refresh_home = binding.refresh_home
        self._workbench_search_service = binding.workbench_search_service
        self._refresh_workbench_search = binding.refresh_workbench_search
        self._refresh_destination_catalogue = binding.refresh_destination_catalogue
        self._account_factories = binding.account_factories
        self._read_account_session = binding.read_account_session
        self._note_activity = binding.note_activity
        self._initial_destination = binding.initial_destination
        self._account_session = binding.initial_account_session
        self._workbench_search_refusal_code = (
            None if binding.workbench_search_service is not None else "workbench.search.unavailable"
        )

    def _start_session(self) -> None:
        factories = self._account_factories
        self._subscribe_session_events(factories)
        if self._unsubscribe_retirement is not None:
            # Revocation and a lost transport arrive as the retirement push; only
            # the expiry, a known instant, and renewal by activity remain to observe.
            self._arm_session_lapse()
        elif self._read_account_session is not None:
            self.set_interval(_SESSION_WATCH_SECONDS, self._watch_account_session)
        self._describe_account_keys()
        if self._account_factories is None:
            self._refuse_account_action()
        if self._initial_destination is not None:
            target, self._initial_destination = self._initial_destination, None
            self._onboarding_offered = True
            self._refresh_account_bars()
            self.navigate_to(target)
            return
        if self._destination_catalogue is not None and self._refresh_home is not None:
            self._show_home(None)

    def _subscribe_session_events(self, factories: AccountFactoriesV1 | None) -> None:
        if factories is not None and factories.subscribe_language is not None:
            self._unsubscribe_language = factories.subscribe_language(self._post_language_invalidated)
        if factories is not None and factories.subscribe_notices is not None:
            self._unsubscribe_notices = factories.subscribe_notices(self._post_upgrade_notice)
        if factories is not None and factories.subscribe_presentation is not None:
            self._unsubscribe_presentation = factories.subscribe_presentation(self._post_presentation_requested)
        if factories is not None and factories.subscribe_retirement is not None:
            self._unsubscribe_retirement = factories.subscribe_retirement(self._post_session_retired)

    def _post_presentation_requested(self, view: ViewLink) -> None:
        self.post_message(PagePresentationRequested(view))

    def on_page_presentation_requested(self, message: PagePresentationRequested) -> None:
        """Open the page the person chose at their desktop, as a palette choice would.

        Over a credential or modal form the request stands down with a notice:
        replacing the destination would discard what that form holds.
        """
        if self._recomposition_pending or self._active_destination_catalogue is None:
            return
        if not self._account_controls_apply():
            notice = tr("tui.root.navigation.busy")
            self.query_one("#root-navigation-refusal", Static).update(notice)
            self.notify(notice, severity="warning")
            return
        self.query_one("#root-navigation-refusal", Static).update("")
        self.navigate_to(presentation_target(message.view))

    def on_runtime_upgrade_pending(self, _: RuntimeUpgradePending) -> None:
        """Render a manager upgrade notice on the existing UI thread."""
        self.notify(tr("common.manager.update_pending"), timeout=10)

    def _post_upgrade_notice(self, _notice: object) -> None:
        self.post_message(RuntimeUpgradePending())

    def on_unmount(self) -> None:
        """Release the event subscription when this profile-bound root leaves."""
        self._stop_session_events()

    def _stop_session_events(self) -> None:
        self._language_epoch += 1
        self._language_pending = False
        self._language_pending_screens.clear()
        if self._language_retry_timer is not None:
            self._language_retry_timer.stop()
            self._language_retry_timer = None
        if self._language_worker is not None:
            self._language_worker.cancel()
            self._language_worker = None
        self._language_refreshing = False
        unsubscribe_language, self._unsubscribe_language = self._unsubscribe_language, None
        if unsubscribe_language is not None:
            unsubscribe_language()
        unsubscribe_presentation, self._unsubscribe_presentation = self._unsubscribe_presentation, None
        if unsubscribe_presentation is not None:
            unsubscribe_presentation()
        unsubscribe_notice, self._unsubscribe_notices = self._unsubscribe_notices, None
        if unsubscribe_notice is not None:
            unsubscribe_notice()
        unsubscribe, self._unsubscribe_retirement = self._unsubscribe_retirement, None
        if unsubscribe is not None:
            unsubscribe()
        if self._session_lapse_timer is not None:
            self._session_lapse_timer.stop()
            self._session_lapse_timer = None

    @property
    def account_session(self) -> HomeAccountSession | None:
        """The session the last Home projection described, once there is one."""
        return self._account_session

    @override
    def refresh_account_chrome(self) -> None:
        """Re-word the account keys and every account bar after a language change."""
        self.query_one("#root-retry", Button).label = tr("tui.root.retry")
        if self._home_refresh_refusal_code is not None:
            self.query_one("#root-read-refusal", Static).update(tr("tui.root.read_unavailable"))
        self._describe_account_keys()
        self._refresh_account_bars()

    @override
    def _refresh_account_bars(self) -> None:
        """Re-word every mounted account bar, beneath the top screen too."""
        for screen in self.screen_stack:
            for bar in screen.query(AccountBar):
                bar.refresh_copy()

    def _refuse_navigation(self) -> None:
        """Expose the localized refusal for an unopenable destination, where it can be seen."""
        message = tr("tui.root.navigation.unavailable")
        self.query_one("#root-navigation-refusal", Static).update(message)
        self.notify(message, severity="warning")

    def _offer_root_retry(self) -> None:
        """Keep an unsuccessful read actionable without discarding the session."""
        message = tr("tui.root.read_unavailable")
        self.query_one("#root-read-refusal", Static).update(message)
        self.query_one("#root-no-areas", Static).display = False
        retry = self.query_one("#root-retry", Button)
        retry.display = True
        retry.disabled = False
        if len(self.screen_stack) == 1:
            retry.focus()
        self.notify(message, severity="warning")
        self.call_after_refresh(self.present_terminal)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Retry a failed bootstrap or Home read through its original read door."""
        if event.button.id != "root-retry":
            return
        event.stop()
        if event.button.disabled or self._recomposition_pending:
            return
        event.button.disabled = True
        event.button.display = False
        self.query_one("#root-read-refusal", Static).update("")
        if self._destination_catalogue is None and self._load_root is not None:
            self.run_worker(self._open_root(self._load_root), group="root-open")
        else:
            self._show_home(self._home_semantic_focus)

    def on_home_target_selected(self, event: HomeTargetSelected) -> None:
        """Open what the selected Home row points at, and remember the row.

        The row is remembered by its domain identity, never its position, so
        the return journey lands on it again. Selecting a row used to do only
        that, which left Home's suggested actions, resumable declarations and
        agenda looking selectable while leading nowhere.
        """
        self._home_semantic_focus = event.target
        target = self._home_row_target(event.target)
        if target is None:
            self._refuse_navigation()
            return
        self.navigate_to(target)

    def on_home_link_selected(self, event: HomeLinkSelected) -> None:
        """Open the page or account control a Home link names."""
        self._open_home_link(event.link)

    def on_home_back_requested(self, _: HomeBackRequested) -> None:
        """Refresh Home after a completed or dismissed journey."""
        if self._refresh_home is not None:
            self._show_home(self._home_semantic_focus)

    async def _show_home_now(self, semantic_focus: HomeTarget | None, navigation_revision: int) -> None:
        """Read Home on a worker thread, then rebuild it on the loop."""
        refresh_home = self._refresh_home
        if refresh_home is None or navigation_revision != self._navigation_revision:
            return
        try:
            refreshed = await await_cancellation_complete(asyncio.to_thread(refresh_home), task_name="tui-home-refresh")
        except AccountSessionExpiredError as error:
            if self._refresh_home is refresh_home and self.is_running:
                self._request_recompose(AccountRecomposeRequiredV1(reason=self._session_failure_reason(error)))
            return
        except Exception as error:
            # A refused refresh is an ordinary outcome, not a crash. The read
            # door refuses when a sibling process writes the profile mid-capture,
            # which is correct and says nothing about this session's validity --
            # the operator keeps the Home they are already looking at and is told
            # the refresh did not happen. The sibling search path already handles
            # its own refusal this way; letting this one escape would end the
            # session with a traceback over a concurrent write.
            diagnostic_event(
                get_logger(__name__),
                "tui_home_refresh_failed",
                fields=diagnostic_error_fields(error),
                primary_error=error,
            )
            if self._home_refresh_is_current(refresh_home, navigation_revision):
                self._home_refresh_refusal_code = "workbench.home.refresh_unavailable"
                self._offer_root_retry()
            return
        if not self._home_refresh_is_current(refresh_home, navigation_revision):
            return
        self._apply_home_refresh(refreshed, semantic_focus)

    def _home_refresh_is_current(self, refresh_home: HomeRefreshDoorV1, navigation_revision: int) -> bool:
        # A severed session, a closing app, or a newer navigation invalidates
        # the result that returned from the worker.
        return (
            self._refresh_home is refresh_home and self.is_running and navigation_revision == self._navigation_revision
        )

    def _apply_home_refresh(
        self, refreshed: RootPresentationV1 | HomeProjectionV1, semantic_focus: HomeTarget | None
    ) -> None:
        projection = refreshed.home if isinstance(refreshed, RootPresentationV1) else refreshed
        if projection.account.posture is HomeSessionPosture.EXPIRED:
            self._request_recompose(AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.EXPIRED))
            return
        if isinstance(refreshed, RootPresentationV1):
            self._destination_catalogue = refreshed.destination_catalogue
            self._active_destination_catalogue = refreshed.destination_catalogue
            self._workbench_search_service = refreshed.workbench_search_service
            self._workbench_search_refusal_code = (
                None if refreshed.workbench_search_service is not None else "workbench.search.unavailable"
            )
            self._account_factories = refreshed.account_factories
        self._home_refresh_refusal_code = None
        self.query_one("#root-read-refusal", Static).update("")
        self.query_one("#root-retry", Button).display = False
        # Home is rebuilt after every return, including from a language
        # change, so this is where the footer catches up with the page.
        self._describe_account_keys()
        self._account_session = projection.account
        self._arm_session_lapse()
        self._refresh_account_bars()
        self.query_one("#root-no-areas", Static).display = False
        if self._destination_catalogue is not None:
            self._active_destination_catalogue = self._destination_catalogue
        self._active_target = None
        self._replace_destination(
            HomeScreen(projection, restore_target=semantic_focus, link_states=self._home_link_states())
        )
        factories = self._account_factories
        if factories is not None and factories.onboarding_pending and not self._onboarding_offered:
            # A profile that is not set up yet cannot prepare a declaration,
            # so the first Home of the session hands straight on to the setup
            # walk. Once only: leaving it returns to Home like any destination.
            self._onboarding_offered = True
            self.call_next(self.run_account_action, AccountActionV1.PROFILE)


__all__ = [
    "CadrumoTuiApp",
]
