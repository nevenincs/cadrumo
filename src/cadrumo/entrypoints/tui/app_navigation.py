"""Navigation and root recomposition for the projection-only TUI app."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from textual.screen import Screen
from textual.widgets import Button, Static

from ...application.search.workbench import WorkbenchDestinationAdmissionState
from ...core.async_cleanup import await_cancellation_complete
from ...core.diagnostic_log import diagnostic_error_fields, diagnostic_event
from ...core.logging import get_logger
from .account import AccountRecomposeReasonV1, AccountRecomposeRequiredV1
from .components.account_chrome import AccountActionV1
from .declarations.controller import (
    CALENDAR_FOCUS_KEY,
    NEW_DECLARATION_FOCUS_KEY,
    SEARCH_DECLARATIONS_FOCUS_KEY,
    calendar_address_focus_key,
)
from .home import (
    HomeLinkV1,
    HomeTarget,
    home_target_action_id,
    home_target_agenda_address,
    home_target_work_unit_id,
)
from .navigation import (
    DestinationFactoryError,
    NavigationContractError,
    TuiDestinationIdV1,
    TuiFocusIdentityV1,
    TuiLeaveGuardV1,
    TuiNavigationTargetV1,
)

if TYPE_CHECKING:
    from .app import CadrumoTuiApp
    from .secret.passphrase import PassphraseScreen


_HOME_LINK_ROUTES: Final[Mapping[HomeLinkV1, tuple[TuiDestinationIdV1, str]]] = MappingProxyType(
    {
        HomeLinkV1.DECLARATIONS: ("workbench.declarations", "navigation.declarations"),
        HomeLinkV1.NEW_DECLARATION: ("workbench.declarations", NEW_DECLARATION_FOCUS_KEY),
        HomeLinkV1.SEARCH_DECLARATIONS: ("workbench.declarations", SEARCH_DECLARATIONS_FOCUS_KEY),
        HomeLinkV1.CALENDAR: ("workbench.declarations", CALENDAR_FOCUS_KEY),
        HomeLinkV1.LEDGER: ("workbench.ledger", "navigation.ledger"),
        HomeLinkV1.AEAT_SYNC: ("workbench.aeat_sync", "navigation.aeat_sync"),
        HomeLinkV1.REFERENCE: ("workbench.reference", "navigation.reference"),
    }
)
"""Where each workbench link on Home leads, with the focus its page opens on."""
_HOME_ACCOUNT_LINK_ACTIONS: Final[Mapping[HomeLinkV1, AccountActionV1]] = MappingProxyType(
    {HomeLinkV1.PROFILE: AccountActionV1.PROFILE, HomeLinkV1.SIGN_OUT: AccountActionV1.SIGN_OUT}
)
"""The account links, performed by the same doors as their keys and palette entries."""


class RootNavigationMixin:
    """Own destination lifecycle, Home restoration, and expired-root teardown."""

    def _home_link_states(self: CadrumoTuiApp) -> dict[HomeLinkV1, WorkbenchDestinationAdmissionState]:
        """Say which of Home's links this session can open, from the catalogue Home was read with."""
        catalogue = self._active_destination_catalogue
        states = {
            link: WorkbenchDestinationAdmissionState.UNAVAILABLE
            if catalogue is None
            else catalogue.resolve(destination).admission.state
            for link, (destination, _focus) in _HOME_LINK_ROUTES.items()
        }
        account = (
            WorkbenchDestinationAdmissionState.UNAVAILABLE
            if self._account_factories is None
            else WorkbenchDestinationAdmissionState.AVAILABLE
        )
        return states | dict.fromkeys(_HOME_ACCOUNT_LINK_ACTIONS, account)

    def _open_home_link(self: CadrumoTuiApp, link: HomeLinkV1) -> None:
        """Open one Home link through the door its keys and palette entry already use."""
        action = _HOME_ACCOUNT_LINK_ACTIONS.get(link)
        if action is not None:
            self.run_account_action(action)
            return
        destination, semantic_key = _HOME_LINK_ROUTES[link]
        self.navigate_to(
            TuiNavigationTargetV1(
                destination=destination,
                focus=TuiFocusIdentityV1(destination=destination, semantic_key=semantic_key),
            )
        )

    def _destination_refuses_leaving(self: CadrumoTuiApp) -> bool:
        """Ask each screen above the root shell, topmost first, whether it may be removed now.

        The first screen that refuses says why on screen, and the caller keeps
        the destination as it is. Every path that pops, replaces or swaps the
        destination, or ends the session at the operator's request, asks here.
        """
        return any(
            isinstance(screen, TuiLeaveGuardV1) and screen.refuse_leaving()
            for screen in reversed(self.screen_stack[1:])
        )

    def navigate_to(self: CadrumoTuiApp, target: TuiNavigationTargetV1, /) -> None:
        """Mount only the current admitted destination with its semantic focus.

        Refused, with the reason on screen, while the destination shown holds
        work it must not abandon.
        """
        if self._destination_refuses_leaving():
            return
        catalogue = self.destination_catalogue
        if target.destination == "workbench.home":
            self._show_home(self._home_semantic_focus)
            return
        try:
            screen = catalogue.create_screen(target)
        except NavigationContractError as error:
            # Factory defects share the contract-error base with expected
            # unavailable routes, but must still produce failure diagnostics.
            if isinstance(error, DestinationFactoryError):
                diagnostic_event(
                    get_logger(__name__),
                    "tui_destination_open_failed",
                    fields={
                        **diagnostic_error_fields(error),
                        "reason_code": target.destination,
                        "outcome": "failed",
                    },
                    primary_error=error,
                )
            self._refuse_navigation()
            return
        except Exception as error:
            # A destination reads its sources as it opens, and the usual reason
            # those reads fail is that the session lapsed while the operator
            # sat on Home. Home's refresh is what tells expiry apart and
            # returns to sign-in; any other failure stays a visible refusal
            # rather than ending the session with a traceback.
            diagnostic_event(
                get_logger(__name__),
                "tui_destination_open_failed",
                fields={**diagnostic_error_fields(error), "reason_code": target.destination, "outcome": "failed"},
                primary_error=error,
            )
            self._refuse_navigation()
            self._show_home(self._home_semantic_focus)
            return
        self._active_target = target
        self._replace_destination(screen, return_to_home=True)

    def _home_row_target(self: CadrumoTuiApp, row: HomeTarget) -> TuiNavigationTargetV1 | None:
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

    def _show_home(self: CadrumoTuiApp, semantic_focus: HomeTarget | None) -> None:
        """Rebuild Home off the event loop and restore its semantic row.

        The Home read can take a whole generation capture. A request made while
        one is out does not read again: it only replaces the row the rebuilt
        Home restores, so the operator's latest position wins.
        """
        if self._refresh_home is None:
            return
        self.query_one("#root-retry", Button).display = False
        self.query_one("#root-read-refusal", Static).update("")
        self._home_request = semantic_focus
        self._navigation_revision += 1
        self._home_navigation_revision = self._navigation_revision
        if self._home_rebuilding:
            return
        self._home_rebuilding = True
        self.query_one("#root-updating", Static).display = True
        self.run_worker(self._rebuild_home(), group="root-home")

    async def _rebuild_home(self: CadrumoTuiApp) -> None:
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

    def _on_destination_dismissed(self: CadrumoTuiApp, _: None) -> None:
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

    async def _return_home(self: CadrumoTuiApp, navigation_revision: int) -> None:
        try:
            await self._rebuild_workbench_search()
            if not self._navigation_is_current(navigation_revision):
                return
            await self._rebuild_destination_catalogue(navigation_revision)
            await self._show_home_now(self._home_semantic_focus, navigation_revision)
        finally:
            self._returning_home = False
            if self.is_running and not self._home_rebuilding:
                self.query_one("#root-updating", Static).display = False

    async def _rebuild_destination_catalogue(self: CadrumoTuiApp, navigation_revision: int) -> None:
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
            refreshed = await await_cancellation_complete(
                asyncio.to_thread(refresh), task_name="tui-destination-refresh"
            )
        except Exception as error:  # a refused re-admission must not end the session
            diagnostic_event(
                get_logger(__name__),
                "tui_destination_refresh_failed",
                fields=diagnostic_error_fields(error),
                primary_error=error,
            )
            if self._refresh_destination_catalogue is refresh and self._navigation_is_current(navigation_revision):
                self._workbench_search_refusal_code = "workbench.destinations.refresh_unavailable"
            return
        if self._refresh_destination_catalogue is not refresh or not self._navigation_is_current(navigation_revision):
            return
        self._destination_catalogue = refreshed
        self._active_destination_catalogue = refreshed

    async def _rebuild_workbench_search(self: CadrumoTuiApp) -> None:
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
        except Exception as error:  # projection failures must not leak protected diagnostics
            diagnostic_event(
                get_logger(__name__),
                "tui_search_refresh_failed",
                fields=diagnostic_error_fields(error),
                primary_error=error,
            )
            if self._refresh_workbench_search is refresh_workbench_search and self.is_running:
                self._workbench_search_refusal_code = "workbench.search.refresh_unavailable"
            return
        if self._refresh_workbench_search is not refresh_workbench_search or not self.is_running:
            return
        self._workbench_search_service = refreshed
        self._workbench_search_refusal_code = None

    def replace_workspace_body(self: CadrumoTuiApp, screen: Screen[None], /) -> None:
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

    def _replace_destination_for_workspace(self: CadrumoTuiApp, screen: Screen[None], navigation_revision: int) -> None:
        """Swap the workspace body from the root's pump so the return survives."""
        if self._navigation_is_current(navigation_revision):
            self._replace_destination(screen, return_to_home=True)

    def _replace_destination(self: CadrumoTuiApp, screen: Screen[None], *, return_to_home: bool = False) -> None:
        """Discard the inactive destination before mounting exactly one replacement.

        The swap runs on this application's pump and waits for each popped
        screen to be removed before pushing. Popping only schedules removal, so
        a replacement carrying the same id as the screen it replaces -- the
        overview re-selected from its own navigation, Home rebuilt over Home --
        was inserted beside it and refused as a duplicate, which ended the
        operator on the empty root.
        """
        self._navigation_revision += 1
        self._swap_revision = self._navigation_revision
        self.call_next(self._swap_destination, screen, return_to_home, self._navigation_revision)

    async def _swap_destination(
        self: CadrumoTuiApp, screen: Screen[None], return_to_home: bool, navigation_revision: int
    ) -> None:
        """Pop every destination, then push the replacement once they are gone.

        The destination is asked again here, at the moment of removal, because
        a replacement can be requested before a write starts and land after
        it: Home reads a whole generation off the loop while the operator can
        still act on the page they are leaving. A refused swap drops the
        replacement and leaves that page, and its write, where they are.

        Account forms are withheld from the request until the old screens are
        gone, and offered again before the replacement is pushed, so one
        opened from then on sits above the new destination.
        """
        try:
            if not self._navigation_is_current(navigation_revision) or self._destination_refuses_leaving():
                return
            while len(self.screen_stack) > 1:
                await self.pop_screen()
                if not self._navigation_is_current(navigation_revision):
                    return
        finally:
            if self._swap_revision == navigation_revision:
                self._swap_revision = None
        await self.push_screen(screen, self._on_destination_dismissed if return_to_home else None)
        self.call_after_refresh(self._record_initial_screen_ready, screen)

    def _navigation_is_current(self: CadrumoTuiApp, navigation_revision: int) -> bool:
        """Recheck navigation and application lifetime across an awaited swap."""
        return navigation_revision == self._navigation_revision and self.is_running

    def _request_recompose(self: CadrumoTuiApp, outcome: AccountRecomposeRequiredV1) -> None:
        """Sever every profile-bound capability before returning to bootstrap.

        The destination is not asked whether it may be left: an expired, lost
        or retired session, or a completed password change, already ended the
        authority any write in flight was submitted under.
        """
        if self._recomposition_pending:
            return
        self._recomposition_pending = True
        password_screen = self._password_screen
        self._sever_profile_root()
        for screen in self.screen_stack[1:]:
            screen.display = False
        if (
            outcome.reason in {AccountRecomposeReasonV1.EXPIRED, AccountRecomposeReasonV1.UNAVAILABLE}
            and password_screen is not None
        ):
            self.run_worker(
                self._settle_expired_password(password_screen, outcome),
                name="password-expiry-settlement",
                exit_on_error=False,
            )
            return
        self.exit(outcome)

    async def _settle_expired_password(
        self: CadrumoTuiApp, screen: PassphraseScreen, outcome: AccountRecomposeRequiredV1
    ) -> None:
        """Keep only completion ownership after the old session has been fenced."""
        completed = await screen.settle_rotation()
        if completed is not None:
            outcome = AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.PASSWORD_CHANGED)
        self._password_screen = None
        if self.is_running:
            self.exit(outcome)

    def _sever_profile_root(self: CadrumoTuiApp) -> None:
        """Invalidate every captured door and queued navigation before any await."""
        self._stop_session_events()
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
        self._note_activity = None
