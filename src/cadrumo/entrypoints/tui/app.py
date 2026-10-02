"""The projection-only navigation join for one dedicated TUI session.

The root receives an immutable Home projection refresh door and a closed,
already-admitted destination catalogue.  It mounts one destination at a time,
returns from real child dismissals to refreshed Home, and preserves the Home
row's semantic identity without taking on business, persistence, or network
authority.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, ClassVar, Final, override

from textual.app import App, ComposeResult, SystemCommand
from textual.binding import Binding
from textual.command import CommandPalette
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Static

from ...application.overview.home import HomeSessionPosture
from ...core.async_cleanup import await_cancellation_complete
from ...core.errors.hierarchy import InternalInvariantError
from ...core.i18n.render import tr
from ...core.logging import get_logger
from ...core.time.clock import now
from ..runtime_management import inspect_installed_runtime_management
from .account import (
    AccountDirectSessionActionV1,
    AccountFactoriesV1,
    AccountRecomposeReasonV1,
    AccountRecomposeRequiredV1,
    AccountSessionExpiredError,
    AccountSessionReaderV1,
    WorkbenchAccountProviderV1,
)
from .components.account_chrome import (
    AccountActionV1,
    AccountBar,
    AccountChromeScreen,
    account_action_label,
    account_key_label,
)
from .components.theme import BASE_CSS, install_cadrumo_themes, toggle_appearance, tokenised
from .declarations.controller import calendar_address_focus_key
from .home import (
    HomeBackRequested,
    HomeScreen,
    HomeTarget,
    HomeTargetSelected,
    home_target_action_id,
    home_target_agenda_address,
    home_target_work_unit_id,
)
from .navigation import (
    NavigationContractError,
    TuiDestinationCatalogueV1,
    TuiFocusIdentityV1,
    TuiNavigationTargetV1,
    TuiScreenContextV1,
)
from .runtime_access_management import RuntimeAccessManagementScreen
from .runtime_management import RuntimeManagementCleanup, RuntimeManagementReader, RuntimeManagementScreen
from .search import WorkbenchCommandProviderV1, WorkbenchSearchDoorV1, WorkbenchSearchProviderV1
from .secret.passphrase import PassphraseScreen

if TYPE_CHECKING:
    from ...application.overview.home import HomeAccountSession, HomeProjectionV1


_ACCOUNT_KEYS: Final[dict[str, AccountActionV1]] = {
    "f2": AccountActionV1.LANGUAGE,
    "f3": AccountActionV1.APPEARANCE,
    "f4": AccountActionV1.PROFILE,
    "f5": AccountActionV1.CHANGE_USER,
    "f6": AccountActionV1.PASSWORD,
    "f7": AccountActionV1.ACCESS,
    "f10": AccountActionV1.SIGN_OUT,
}
"""The key for each account control, reachable from every destination."""

_SESSION_WATCH_SECONDS: Final = 30.0
"""How often the root checks whether the session has lapsed."""


@dataclass(frozen=True, slots=True)
class RootPresentationV1:
    """One captured Home and its matching destination, search, and account doors."""

    home: HomeProjectionV1
    destination_catalogue: TuiDestinationCatalogueV1
    workbench_search_service: WorkbenchSearchDoorV1 | None
    account_factories: AccountFactoriesV1


type HomeRefreshDoorV1 = Callable[[], HomeProjectionV1 | RootPresentationV1]
type WorkbenchSearchRefreshDoorV1 = Callable[[], WorkbenchSearchDoorV1]
type DestinationCatalogueRefreshDoorV1 = Callable[[], TuiDestinationCatalogueV1]


@dataclass(frozen=True, slots=True)
class RootBindingV1:
    """Every door the root needs for one authenticated session, built off the loop."""

    destination_catalogue: TuiDestinationCatalogueV1
    refresh_home: HomeRefreshDoorV1
    workbench_search_service: WorkbenchSearchDoorV1 | None
    refresh_workbench_search: WorkbenchSearchRefreshDoorV1 | None
    refresh_destination_catalogue: DestinationCatalogueRefreshDoorV1 | None
    account_factories: AccountFactoriesV1
    read_account_session: AccountSessionReaderV1 | None


type RootLoaderV1 = Callable[[], RootBindingV1]


class CadrumoTuiApp(App[AccountRecomposeRequiredV1 | None]):
    """Host one composed TUI session and whichever areas are joinable."""

    CSS = tokenised(
        BASE_CSS
        + """
    #root-updating { display: none; padding: $cadrumo-space-0 $cadrumo-gutter; }
    #root-account-refusal, #root-navigation-refusal {
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
            for key, action in _ACCOUNT_KEYS.items()
        ),
        Binding("q", "quit", "", show=False),
    ]
    COMMANDS = App.COMMANDS | {WorkbenchSearchProviderV1, WorkbenchCommandProviderV1, WorkbenchAccountProviderV1}

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
        load_root: RootLoaderV1 | None = None,
        runtime_management_reader: RuntimeManagementReader = inspect_installed_runtime_management,
        runtime_management_cleanup: RuntimeManagementCleanup | None = None,
    ) -> None:
        """Bind the shell to caller-owned doors.

        ``load_root`` replaces the individual doors. The shell renders first,
        and a worker thread builds the first generation so opening the
        workbench never freezes the terminal.
        """
        super().__init__()
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
        self._load_root = load_root
        """Builds the workbench root off the event loop once the shell has rendered."""
        self._runtime_management_reader = runtime_management_reader
        self._runtime_management_cleanup = (
            RuntimeManagementCleanup() if runtime_management_cleanup is None else runtime_management_cleanup
        )
        self._refresh_destination_catalogue = refresh_destination_catalogue
        self._account_factories = account_factories
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
        self._read_account_session = read_account_session
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

    @property
    def workbench_search_service(self) -> WorkbenchSearchDoorV1:
        """Return the caller-composed application search door for the palette."""
        if self._workbench_search_service is None:
            raise InternalInvariantError("the root has no composed workbench search service")
        return self._workbench_search_service

    @property
    def home_refresh_refusal_code(self) -> str | None:
        """Expose only a sanitized refusal code for host presentation."""
        return self._home_refresh_refusal_code

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
        try:
            binding = await await_cancellation_complete(asyncio.to_thread(load_root), task_name="tui-root-load")
        except AccountSessionExpiredError:
            if self._load_root is load_root and self.is_running:
                self._request_recompose(AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.EXPIRED))
            return
        except Exception:
            if self._load_root is load_root and self.is_running:
                self._home_refresh_refusal_code = "workbench.home.refresh_unavailable"
                self.query_one("#root-updating", Static).display = False
                self._refuse_account_action()
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
        self._workbench_search_refusal_code = (
            None if binding.workbench_search_service is not None else "workbench.search.unavailable"
        )

    def _start_session(self) -> None:
        if self._read_account_session is not None:
            self.set_interval(_SESSION_WATCH_SECONDS, self._watch_account_session)
        self._describe_account_keys()
        if self._account_factories is None:
            self._refuse_account_action()
        if self._destination_catalogue is not None and self._refresh_home is not None:
            self._show_home(None)

    @property
    def account_actions_available(self) -> bool:
        """Whether the account controls can act right now.

        False without account doors, and while a credential or modal screen is
        open, so the palette withholds them exactly where the keys are hidden.
        """
        return self._account_factories is not None and self._account_controls_apply()

    def account_action_available(self, action: AccountActionV1, /) -> bool:
        """Offer only account controls backed by this root's installed doors."""
        factories = self._account_factories
        if factories is None or not self._account_controls_apply():
            return False
        if action is AccountActionV1.PASSWORD:
            return factories.password is not None
        if action is AccountActionV1.ACCESS:
            return factories.access is not None
        return True

    @property
    def account_session(self) -> HomeAccountSession | None:
        """The session the last Home projection described, once there is one."""
        return self._account_session

    def _watch_account_session(self) -> None:
        """End the session once it has lapsed, without waiting for the operator to act.

        Any failure to confirm the session fails closed: a session that cannot
        be shown to be live is treated as expired, never as still open.
        """
        if self._read_account_session is None or self._account_session is None or self._account_session_polling:
            return
        self._account_session_polling = True
        self.run_worker(self._poll_account_session(), name="account-session-watch", exclusive=True)

    async def _poll_account_session(self) -> None:
        """Observe one session off the UI task and discard a stale root's result."""
        reader = self._read_account_session
        if reader is None:
            self._account_session_polling = False
            return
        try:
            session = await reader()
        except Exception:
            if self._read_account_session is reader:
                self._request_recompose(AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.EXPIRED))
            return
        finally:
            self._account_session_polling = False
        if (
            session.posture is not HomeSessionPosture.ACTIVE
            or session.expires_at is None
            or session.expires_at <= now()
        ):
            if self._read_account_session is reader:
                self._request_recompose(AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.EXPIRED))
            return
        if (
            self._read_account_session is reader
            and self._account_session is not None
            and session.expires_at != self._account_session.expires_at
        ):
            self._account_session = session
            self._refresh_account_bars()

    def refresh_account_chrome(self) -> None:
        """Re-word the account keys and every account bar after a language change."""
        self._describe_account_keys()
        self._refresh_account_bars()

    def _refresh_account_bars(self) -> None:
        """Re-word every mounted account bar, beneath the top screen too."""
        for screen in self.screen_stack:
            for bar in screen.query(AccountBar):
                bar.refresh_copy()

    def _account_controls_apply(self) -> bool:
        """Whether the screen the operator is on is one account controls act from.

        They act from a destination or the bare root. Over a credential or
        modal screen -- the password form, a login, the sign-out progress --
        they would stack a second form on the first, so they stand down until
        it closes. The command palette is looked past: it is opened over the
        screen the operator is actually on.
        """
        screen = next(
            (candidate for candidate in reversed(self.screen_stack) if not isinstance(candidate, CommandPalette)),
            None,
        )
        return screen is None or screen is self.screen_stack[0] or isinstance(screen, AccountChromeScreen)

    @override
    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Hide the account keys wherever the controls would not act."""
        if action == "account":
            if len(parameters) != 1 or not isinstance(parameters[0], str):
                return False
            try:
                return self.account_action_available(AccountActionV1(parameters[0]))
            except ValueError:
                return False
        return True

    def _describe_account_keys(self) -> None:
        """Name every account key in the footer, in the language now on screen.

        Replaced by assignment on this instance's own table, for the reason
        ``ProfileManagerScreen._offer_language_in_footer`` gives: Textual's
        ``bind`` appends, and the table's lists are shared with the class. A
        session without account doors shows only the appearance key, which
        needs no profile; advertising the others would promise a refusal.
        """
        for key, action in _ACCOUNT_KEYS.items():
            bindings = self._bindings.key_to_bindings.get(key)
            if bindings is None:
                continue
            # Appearance stays bound and in the palette but leaves the footer:
            # the footer must hold the other five keys at eighty columns.
            shown = action is not AccountActionV1.APPEARANCE and self.account_action_available(action)
            self._bindings.key_to_bindings[key] = [
                replace(binding, description=account_key_label(action), show=shown) for binding in bindings
            ]
        self.refresh_bindings()

    @override
    def get_system_commands(self, screen: Screen[object]) -> Iterable[SystemCommand]:
        """Offer only Cadrumo's own session commands, in the operator's language.

        Textual's defaults are English whatever the page says, and its theme
        switcher leaves Cadrumo's light and dark pair for themes the product
        does not style. Appearance is listed here rather than with the account
        controls because it needs no profile.
        """
        yield SystemCommand(
            account_action_label(AccountActionV1.APPEARANCE),
            tr("tui.root.account_help.appearance"),
            self.action_toggle_appearance,
        )
        if self._account_controls_apply():
            yield SystemCommand(
                tr("tui.runtime_management.open"),
                tr("tui.runtime_management.open_help"),
                self.action_runtime_management,
            )
        yield SystemCommand(tr("tui.root.system.quit"), tr("tui.root.system.quit_help"), self.action_quit)

    @override
    def action_command_palette(self) -> None:
        """Open the palette with its prompt in the operator's language."""
        if self.use_command_palette and not any(
            isinstance(open_screen, CommandPalette) for open_screen in self.screen_stack
        ):
            self.push_screen(CommandPalette(id="--command-palette", placeholder=tr("tui.root.palette.placeholder")))

    def action_toggle_appearance(self) -> None:
        """Flip between the light and dark appearance."""
        toggle_appearance(self)

    def action_runtime_management(self) -> None:
        """Open a profile-free passive status panel outside active modal work."""
        if self._account_controls_apply():
            self.push_screen(
                RuntimeManagementScreen(
                    reader=self._runtime_management_reader, cleanup=self._runtime_management_cleanup
                )
            )

    def action_account(self, action: str) -> None:
        """Run the account control a key names."""
        self.run_account_action(AccountActionV1(action))

    def run_account_action(self, action: AccountActionV1, /) -> None:
        """Perform one account control through the session's injected doors.

        Every surface that offers a control -- the keys, the palette -- ends
        here, so none of them can reach a door the others cannot, or refuse
        differently.
        """
        factories = self._account_factories
        if factories is None:
            self._refuse_account_action()
            return
        if not self.account_action_available(action):
            self._refuse_account_action()
            return
        match action:
            case AccountActionV1.CHANGE_USER:
                self._start_direct_session_action(
                    factories.change_user(), expected=AccountRecomposeReasonV1.CHANGE_USER
                )
            case AccountActionV1.PASSWORD:
                if factories.password is not None:
                    password_screen = factories.password()
                    self._password_screen = password_screen
                    self.push_screen(password_screen, self._on_password_dismissed)
            case AccountActionV1.ACCESS:
                if factories.access is not None:
                    access_screen = factories.access()
                    self.push_screen(access_screen, lambda _: self._on_access_dismissed(access_screen))
            case AccountActionV1.PROFILE:
                self.navigate_to(
                    TuiNavigationTargetV1(
                        destination="workbench.profile",
                        focus=TuiFocusIdentityV1(
                            destination="workbench.profile",
                            semantic_key="profile.overview",
                        ),
                    )
                )
            case AccountActionV1.APPEARANCE:
                factories.appearance(self)
            case AccountActionV1.LANGUAGE:
                screen = factories.profile(TuiScreenContextV1(destination="workbench.profile"))
                self._replace_destination(screen, return_to_home=True)
                self.call_after_refresh(factories.language, screen)
            case AccountActionV1.SIGN_OUT:
                try:
                    sign_out = factories.sign_out()
                except Exception:
                    self._refuse_account_action()
                    return
                self._start_direct_session_action(sign_out, expected=AccountRecomposeReasonV1.SIGNED_OUT)

    def _on_access_dismissed(self, screen: Screen[None]) -> None:
        """Retire known-lost access immediately; otherwise recheck live status."""
        if isinstance(screen, RuntimeAccessManagementScreen) and screen.access_lost:
            for private_screen in self.screen_stack[1:]:
                private_screen.display = False
            self._request_recompose(AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.EXPIRED))
        else:
            self._watch_account_session()

    def _on_password_dismissed(self, outcome: object | None) -> None:
        """Discard this root after an authenticated custody-generation change."""
        from ...application.user_profile.passphrase_rotation import ProfilePassphraseRotationOutcome

        self._password_screen = None
        if isinstance(outcome, ProfilePassphraseRotationOutcome):
            self._request_recompose(AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.PASSWORD_CHANGED))

    def _start_direct_session_action(
        self, action: AccountDirectSessionActionV1, *, expected: AccountRecomposeReasonV1
    ) -> None:
        """Remove the old profile authority before starting a runtime effect."""
        self._sever_profile_root()
        for screen in self.screen_stack[1:]:
            screen.display = False
        self.run_worker(self._complete_direct_session_action(action, expected=expected), name="account-direct-action")

    async def _complete_direct_session_action(
        self, action: AccountDirectSessionActionV1, *, expected: AccountRecomposeReasonV1
    ) -> None:
        """Drain private screens and the effect even if this worker is cancelled."""
        outcome = AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.EXPIRED)
        try:
            while len(self.screen_stack) > 1:
                await await_cancellation_complete(self.pop_screen(), task_name="account-direct-screen-pop")
            completed = await await_cancellation_complete(action.complete(), task_name="account-direct-completion")
            if completed.reason is expected:
                outcome = completed
        except (Exception, asyncio.CancelledError):
            get_logger(__name__).warning("account direct action could not complete")
        if self.is_running:
            self.exit(outcome)

    def _refuse_account_action(self) -> None:
        """Expose one localized fail-closed message without exception details.

        Written to the root shell and also raised as a notification: the shell
        sits beneath every destination, so a refusal written only there was
        never seen by an operator who was on Home or in a workspace.
        """
        message = tr("tui.root.account.unavailable")
        self.query_one("#root-account-refusal", Static).update(message)
        self.notify(message, severity="warning")

    def _refuse_navigation(self) -> None:
        """Expose the localized refusal for an unopenable destination, where it can be seen."""
        message = tr("tui.root.navigation.unavailable")
        self.query_one("#root-navigation-refusal", Static).update(message)
        self.notify(message, severity="warning")

    def navigate_to(self, target: TuiNavigationTargetV1, /) -> None:
        """Mount only the current admitted destination with its semantic focus."""
        catalogue = self.destination_catalogue
        if target.destination == "workbench.home":
            self._show_home(self._home_semantic_focus)
            return
        try:
            screen = catalogue.create_screen(target)
        except NavigationContractError:
            self._refuse_navigation()
            return
        except Exception:
            # A destination reads its sources as it opens, and the usual reason
            # those reads fail is that the session lapsed while the operator
            # sat on Home. Home's refresh is what tells expiry apart and
            # returns to sign-in; any other failure stays a visible refusal
            # rather than ending the session with a traceback.
            get_logger(__name__).warning("destination %s could not open", target.destination)
            self._refuse_navigation()
            self._show_home(self._home_semantic_focus)
            return
        self._active_target = target
        self._replace_destination(screen, return_to_home=True)

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

    def _home_row_target(self, row: HomeTarget) -> TuiNavigationTargetV1 | None:
        """Translate one Home row into the admitted destination it belongs to."""
        action_id = home_target_action_id(row)
        if action_id is not None:
            for route in self.destination_catalogue.routes:
                if route.admission.state.value != "available":
                    continue
                if any(candidate.action_candidate_id == action_id for candidate in route.action_candidates):
                    destination = route.descriptor.destination
                    return TuiNavigationTargetV1(
                        destination=destination,
                        focus=TuiFocusIdentityV1(destination=destination, semantic_key=f"action.{action_id}"),
                        action_candidate_id=action_id,
                    )
            return None
        work_unit_id = home_target_work_unit_id(row)
        if work_unit_id is not None:
            try:
                focus = TuiFocusIdentityV1(
                    destination="workbench.declarations",
                    semantic_key="declarations.work",
                    restore_token=work_unit_id,
                )
            except ValueError:
                # An identity the focus contract cannot carry still opens the
                # declarations; only the row restore is lost.
                focus = TuiFocusIdentityV1(destination="workbench.declarations", semantic_key="declarations.work")
            return TuiNavigationTargetV1(destination="workbench.declarations", focus=focus)
        address = home_target_agenda_address(row)
        if address is not None:
            return TuiNavigationTargetV1(
                destination="workbench.declarations",
                focus=TuiFocusIdentityV1(
                    destination="workbench.declarations",
                    semantic_key=calendar_address_focus_key(*address),
                ),
            )
        return None

    def on_home_back_requested(self, _: HomeBackRequested) -> None:
        """Refresh Home after a completed or dismissed journey."""
        if self._refresh_home is not None:
            self._show_home(self._home_semantic_focus)

    def _show_home(self, semantic_focus: HomeTarget | None) -> None:
        """Rebuild Home off the event loop and restore its semantic row.

        The Home read can take a whole generation capture. A request made while
        one is out does not read again: it only replaces the row the rebuilt
        Home restores, so the operator's latest position wins.
        """
        if self._refresh_home is None:
            return
        self._home_request = semantic_focus
        self._navigation_revision += 1
        self._home_navigation_revision = self._navigation_revision
        if self._home_rebuilding:
            return
        self._home_rebuilding = True
        self.query_one("#root-updating", Static).display = True
        self.run_worker(self._rebuild_home(), group="root-home")

    async def _rebuild_home(self) -> None:
        try:
            while self._home_navigation_revision == self._navigation_revision:
                revision = self._home_navigation_revision
                await self._show_home_now(self._home_request, revision)
                if revision == self._home_navigation_revision:
                    break
        finally:
            self._home_rebuilding = False
            if self.is_running and not self._returning_home:
                self.query_one("#root-updating", Static).display = False

    async def _show_home_now(self, semantic_focus: HomeTarget | None, navigation_revision: int) -> None:
        """Read Home on a worker thread, then rebuild it on the loop."""
        refresh_home = self._refresh_home
        if refresh_home is None or navigation_revision != self._navigation_revision:
            return
        try:
            refreshed = await await_cancellation_complete(asyncio.to_thread(refresh_home), task_name="tui-home-refresh")
        except AccountSessionExpiredError:
            if self._refresh_home is refresh_home and self.is_running:
                self._request_recompose(AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.EXPIRED))
            return
        except Exception:
            # A refused refresh is an ordinary outcome, not a crash. The read
            # door refuses when a sibling process writes the profile mid-capture,
            # which is correct and says nothing about this session's validity --
            # the operator keeps the Home they are already looking at and is told
            # the refresh did not happen. The sibling search path already handles
            # its own refusal this way; letting this one escape would end the
            # session with a traceback over a concurrent write.
            if self._refresh_home is refresh_home and self.is_running:
                self._home_refresh_refusal_code = "workbench.home.refresh_unavailable"
                self._refuse_account_action()
            return
        if (
            self._refresh_home is not refresh_home
            or not self.is_running
            or navigation_revision != self._navigation_revision
        ):
            # The session was severed or the app is closing while the read was
            # out, or a newer explicit navigation owns the visible screen.
            return
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
        # Home is rebuilt after every return, including from a language
        # change, so this is where the footer catches up with the page.
        self._describe_account_keys()
        self._account_session = projection.account
        self._refresh_account_bars()
        self.query_one("#root-no-areas", Static).display = False
        if self._destination_catalogue is not None:
            self._active_destination_catalogue = self._destination_catalogue
        self._active_target = None
        self._replace_destination(HomeScreen(projection, restore_target=semantic_focus))
        factories = self._account_factories
        if factories is not None and factories.onboarding_pending and not self._onboarding_offered:
            # A profile that is not set up yet cannot prepare a declaration,
            # so the first Home of the session hands straight on to the setup
            # walk. Once only: leaving it returns to Home like any destination.
            self._onboarding_offered = True
            self.call_next(self.run_account_action, AccountActionV1.PROFILE)

    def _on_destination_dismissed(self, _: None) -> None:
        """Return from a real child dismissal through the projection refresh door.

        The refresh reads a whole new generation, which takes seconds on a real
        profile, so it runs off the event loop and the rest of the return
        continues on the loop once it lands. A second return while one is out
        joins it rather than reading the store again.
        """
        if self._returning_home:
            return
        self._returning_home = True
        self._navigation_revision += 1
        self.query_one("#root-updating", Static).display = True
        self.run_worker(self._return_home(self._navigation_revision), group="root-return-home")

    async def _return_home(self, navigation_revision: int) -> None:
        try:
            await self._rebuild_workbench_search()
            self._rebuild_destination_catalogue()
            await self._show_home_now(self._home_semantic_focus, navigation_revision)
        finally:
            self._returning_home = False
            if self.is_running:
                self.query_one("#root-updating", Static).display = False

    def _rebuild_destination_catalogue(self) -> None:
        """Re-admit destinations against the generation the factories now read.

        Availability is a property of the CURRENT capture, not of the first
        one. A profile that declares its NIF mid-session makes AEAT Sync
        readable, and one that clears it makes it unreadable again; a frozen
        catalogue would keep offering a route whose projection is gone, or keep
        refusing one that has since become available.
        """
        refresh = self._refresh_destination_catalogue
        if refresh is None or self._destination_catalogue is None:
            return
        try:
            refreshed = refresh()
        except Exception:  # a refused re-admission must not end the session
            self._workbench_search_refusal_code = "workbench.destinations.refresh_unavailable"
            return
        self._destination_catalogue = refreshed
        self._active_destination_catalogue = refreshed

    async def _rebuild_workbench_search(self) -> None:
        """Replace search only after the owning child has authoritatively returned.

        The capture behind the refresh reads a whole generation, so it runs on
        a worker thread and only the replacement happens on the event loop.
        """
        refresh_workbench_search = self._refresh_workbench_search
        if refresh_workbench_search is None:
            return
        try:
            refreshed = await await_cancellation_complete(
                asyncio.to_thread(refresh_workbench_search), task_name="tui-search-refresh"
            )
        except Exception:  # projection failures must not leak protected diagnostics
            if self._refresh_workbench_search is refresh_workbench_search and self.is_running:
                self._workbench_search_refusal_code = "workbench.search.refresh_unavailable"
            return
        if self._refresh_workbench_search is not refresh_workbench_search or not self.is_running:
            return
        self._workbench_search_service = refreshed
        self._workbench_search_refusal_code = None

    def replace_workspace_body(self, screen: Screen[None], /) -> None:
        """Show another body of the destination the operator is already inside.

        The destination does not change, so the return journey does not either:
        the replacement keeps the same dismissal callback, and Escape from any
        internal body returns to Home exactly as it does from the entry body.
        The root never learns which body this is -- the workspace resolved it.

        The swap is deferred onto this application's own message pump, and that
        is load-bearing rather than tidiness. A screen's result callback is
        dispatched through whichever pump was active when the screen was
        pushed, so pushing directly from inside the outgoing screen's handler
        registers the return journey against a screen that is about to be
        popped. The callback then belongs to a stopped pump and never runs, and
        Escape from an internal area strands the operator on an empty root with
        no way back.
        """
        self.call_next(self._replace_destination_for_workspace, screen, self._navigation_revision)

    def _replace_destination_for_workspace(self, screen: Screen[None], navigation_revision: int) -> None:
        """Swap the workspace body from the root's pump so the return survives."""
        if self._navigation_is_current(navigation_revision):
            self._replace_destination(screen, return_to_home=True)

    def _replace_destination(self, screen: Screen[None], *, return_to_home: bool = False) -> None:
        """Discard the inactive destination before mounting exactly one replacement.

        The swap runs on this application's pump and waits for each popped
        screen to be removed before pushing. Popping only schedules removal, so
        a replacement carrying the same id as the screen it replaces -- the
        overview re-selected from its own navigation, Home rebuilt over Home --
        was inserted beside it and refused as a duplicate, which ended the
        operator on the empty root.
        """
        self._navigation_revision += 1
        self.call_next(self._swap_destination, screen, return_to_home, self._navigation_revision)

    async def _swap_destination(self, screen: Screen[None], return_to_home: bool, navigation_revision: int) -> None:
        """Pop every destination, then push the replacement once they are gone."""
        if not self._navigation_is_current(navigation_revision):
            return
        while len(self.screen_stack) > 1:
            await self.pop_screen()
            if not self._navigation_is_current(navigation_revision):
                return
        await self.push_screen(screen, self._on_destination_dismissed if return_to_home else None)

    def _navigation_is_current(self, navigation_revision: int) -> bool:
        """Recheck navigation and application lifetime across an awaited swap."""
        return navigation_revision == self._navigation_revision and self.is_running

    def _request_recompose(self, outcome: AccountRecomposeRequiredV1) -> None:
        """Sever every profile-bound capability before returning to bootstrap."""
        if self._recomposition_pending:
            return
        self._recomposition_pending = True
        password_screen = self._password_screen
        self._sever_profile_root()
        for screen in self.screen_stack[1:]:
            screen.display = False
        if outcome.reason is AccountRecomposeReasonV1.EXPIRED and password_screen is not None:
            self.run_worker(
                self._settle_expired_password(password_screen, outcome),
                name="password-expiry-settlement",
                exit_on_error=False,
            )
            return
        self.exit(outcome)

    async def _settle_expired_password(self, screen: PassphraseScreen, outcome: AccountRecomposeRequiredV1) -> None:
        """Keep only completion ownership after the old session has been fenced."""
        completed = await screen.settle_rotation()
        if completed is not None:
            outcome = AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.PASSWORD_CHANGED)
        self._password_screen = None
        if self.is_running:
            self.exit(outcome)

    def _sever_profile_root(self) -> None:
        """Invalidate every captured door and queued navigation before any await."""
        self._navigation_revision += 1
        self._load_root = None
        self._account_session = None
        self._account_factories = None
        self._destination_catalogue = None
        self._active_destination_catalogue = None
        self._refresh_home = None
        self._workbench_search_service = None
        self._refresh_workbench_search = None
        self._refresh_destination_catalogue = None
        self._active_target = None
        self._home_semantic_focus = None
        self._home_request = None
        self._read_account_session = None


__all__ = [
    "CadrumoTuiApp",
    "DestinationCatalogueRefreshDoorV1",
    "HomeRefreshDoorV1",
    "RootBindingV1",
    "RootLoaderV1",
    "RootPresentationV1",
    "WorkbenchSearchRefreshDoorV1",
]
