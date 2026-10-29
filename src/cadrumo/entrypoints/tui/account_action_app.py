"""Account controls and direct session actions for the TUI root."""

from __future__ import annotations

import asyncio
from abc import abstractmethod
from collections.abc import Iterable
from dataclasses import replace
from typing import TYPE_CHECKING, Final, override

from textual.app import SystemCommand
from textual.command import CommandPalette
from textual.screen import Screen
from textual.widgets import Static

from ...core.async_cleanup import await_cancellation_complete
from ...core.i18n.render import tr
from ...core.logging import get_logger
from .account import (
    AccountAccessState,
    AccountDirectSessionActionV1,
    AccountFactoriesV1,
    AccountRecomposeReasonV1,
    AccountRecomposeRequiredV1,
)
from .account_session_app import AccountSessionApp
from .components.account_chrome import AccountActionV1, AccountChromeScreen, account_action_label, account_key_label
from .components.theme import toggle_appearance
from .navigation import TuiFocusIdentityV1, TuiNavigationTargetV1, TuiScreenContextV1

if TYPE_CHECKING:
    from .secret.passphrase import PassphraseScreen


ACCOUNT_KEYS: Final[dict[str, AccountActionV1]] = {
    "f2": AccountActionV1.LANGUAGE,
    "f3": AccountActionV1.APPEARANCE,
    "f4": AccountActionV1.PROFILE,
    "f5": AccountActionV1.CHANGE_USER,
    "f6": AccountActionV1.PASSWORD,
    "f7": AccountActionV1.ACCESS,
    "f10": AccountActionV1.SIGN_OUT,
}
"""The key for each account control, reachable from every destination."""

_LEAVING_ACCOUNT_ACTIONS: Final = frozenset(
    {
        AccountActionV1.PROFILE,
        AccountActionV1.LANGUAGE,
        AccountActionV1.CHANGE_USER,
        AccountActionV1.PASSWORD,
        AccountActionV1.SIGN_OUT,
    }
)
"""The account controls that remove the destination shown, so it is asked first.

Profile and Language replace it. Change user and Sign out end the session. A
completed password change ends it too, so the form is not opened over work
that must not be abandoned. Appearance and Access leave the destination
mounted; Access ends the session only when the runtime reports the access
lost, which cannot be refused.
"""


class AccountActionApp(AccountSessionApp):
    """Admit account controls and complete their owned session effects."""

    _swap_revision: int | None
    _recomposition_pending: bool
    _password_screen: PassphraseScreen | None

    @abstractmethod
    def _destination_refuses_leaving(self) -> bool:
        """Ask whether the current destination can be left."""

    @abstractmethod
    def navigate_to(self, target: TuiNavigationTargetV1, /) -> None:
        """Navigate to an admitted destination."""

    @abstractmethod
    def _replace_destination(self, screen: Screen[None], *, return_to_home: bool = False) -> None:
        """Replace the current destination."""

    @abstractmethod
    def _sever_profile_root(self) -> None:
        """Remove the current profile authority."""

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

    def _account_controls_apply(self) -> bool:
        """Whether the screen the operator is on is one account controls act from.

        They act from a destination or the bare root. Over a credential or
        modal screen -- the password form, a login, the sign-out progress --
        they would stack a second form on the first, so they stand down until
        it closes. The command palette is looked past: it is opened over the
        screen the operator is actually on.

        They also stand down while the root is replacing its destination. The
        swap removes every screen above the root shell once it runs, so a form
        opened after it was requested -- typed ahead during startup, or while
        Home lands -- would be removed with the destination it covered.
        """
        if self._swap_revision is not None:
            return False
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
        for key, action in ACCOUNT_KEYS.items():
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

    @override
    async def action_quit(self) -> None:
        """Quit, unless the destination shown holds work it must not abandon.

        Every quit the operator asks for ends here: the key, Ctrl+Q and the
        palette's Quit command.
        """
        if self._destination_refuses_leaving():
            return
        await super().action_quit()

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
        if factories is None or not self.account_action_available(action):
            self._refuse_account_action()
            return
        if action in _LEAVING_ACCOUNT_ACTIONS and self._destination_refuses_leaving():
            return
        self._dispatch_account_action(factories, action)

    def _dispatch_account_action(self, factories: AccountFactoriesV1, action: AccountActionV1) -> None:
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
                self._dispatch_sign_out(factories)

    def _dispatch_sign_out(self, factories: AccountFactoriesV1) -> None:
        try:
            sign_out = factories.sign_out()
        except Exception:
            self._refuse_account_action()
            return
        self._start_direct_session_action(sign_out, expected=AccountRecomposeReasonV1.SIGNED_OUT)

    def _on_access_dismissed(self, screen: Screen[None]) -> None:
        """Retire known-lost access immediately; otherwise recheck live status."""
        if isinstance(screen, AccountAccessState) and screen.access_lost:
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
        if self._recomposition_pending:
            return
        # A queued retirement notification must not overtake the owned logout
        # completion and destroy its connection before the acknowledgement.
        self._recomposition_pending = True
        self._sever_profile_root()
        for screen in self.screen_stack[1:]:
            screen.display = False
        self.run_worker(self._complete_direct_session_action(action, expected=expected), name="account-direct-action")

    async def _complete_direct_session_action(
        self, action: AccountDirectSessionActionV1, *, expected: AccountRecomposeReasonV1
    ) -> None:
        """Drain private screens and the effect even if this worker is cancelled."""
        outcome = AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.UNAVAILABLE)
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
