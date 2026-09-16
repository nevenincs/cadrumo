"""The account chrome every workbench destination carries.

The account controls are performed by the workbench root; this module names
them, declares the seam the root offers, and draws the one-line status bar and
key footer that sit around each destination.
"""

from __future__ import annotations

from dataclasses import replace
from enum import StrEnum, auto
from typing import TYPE_CHECKING, ClassVar, Final, Protocol, runtime_checkable

from textual import events, on
from textual.screen import Screen
from textual.widgets import Footer, Static

from ....application.overview.home import HomeSessionPosture
from ....core.i18n.render import tr
from .theme import tokenised

if TYPE_CHECKING:
    from ....application.overview.home import HomeAccountSession


class AccountActionV1(StrEnum):
    """One account control the workbench offers, whatever surface invoked it.

    The value doubles as the locale leaf under ``tui.root.account`` (the
    control's name) and ``tui.root.account_help`` (what it does).
    """

    LANGUAGE = auto()
    APPEARANCE = auto()
    PROFILE = auto()
    CHANGE_USER = auto()
    PASSWORD = auto()
    SIGN_OUT = auto()


def account_action_label(action: AccountActionV1) -> str:
    """Name one account control in the language now on screen."""
    return tr(f"tui.root.account.{action.value}")


def account_key_label(action: AccountActionV1) -> str:
    """Name one account control briefly, for the key footer.

    The footer has to hold every account key on an eighty-column terminal, so
    it uses short names; the palette and help keep the full ones.
    """
    return tr(f"tui.root.account_key.{action.value}")


def account_action_help(action: AccountActionV1) -> str:
    """Describe what one account control does, in the language now on screen."""
    return tr(f"tui.root.account_help.{action.value}")


@runtime_checkable
class TuiAccountHostV1(Protocol):
    """The root seam through which every account control is dispatched."""

    @property
    def account_actions_available(self) -> bool:
        """Whether the account controls can act from the screen now in front."""
        ...

    @property
    def account_session(self) -> HomeAccountSession | None:
        """The session the last Home projection described, once there is one."""
        ...

    def run_account_action(self, action: AccountActionV1, /) -> None:
        """Perform one account control through the session's injected doors."""
        ...

    def refresh_account_chrome(self) -> None:
        """Re-word the account keys and bars after the page language changed."""
        ...


_APPEARANCE_KEY: Final = "f3"
"""The appearance key, the one account control a destination may bind itself."""

_SESSION_LOCALE_KEYS: Final[dict[HomeSessionPosture, str]] = {
    HomeSessionPosture.NO_PROFILE: "tui.home.session.no_profile",
    HomeSessionPosture.LOCKED: "tui.home.session.locked",
    HomeSessionPosture.ACTIVE: "tui.home.session.active",
    HomeSessionPosture.EXPIRED: "tui.home.session.expired",
}


def account_status_line(session: HomeAccountSession | None) -> str:
    """Say who is signed in, in what state, and until when if that is known."""
    if session is None:
        return tr("tui.root.account.default_profile")
    # Kept short: the bar is one row, and on an eighty-column terminal a
    # longer line loses its end -- which is where the expiry time sits.
    label = session.profile_label or tr("tui.home.account_fallback")
    status = tr(_SESSION_LOCALE_KEYS[session.posture])
    if session.expires_at is None:
        return tr("tui.root.account_bar.line", label=label, status=status)
    return tr(
        "tui.root.account_bar.line_with_expiry",
        label=label,
        status=status,
        expires_at=session.expires_at.strftime("%H:%M UTC"),
    )


class AccountBar(Static):
    """One status line above every destination: the signed-in profile and its session.

    The controls themselves are reached through the key footer and the
    command palette, so the bar spends one row, not three. Hosted anywhere but
    the workbench root -- a standalone screen host -- it shows only the
    generic account label, because there is no session to describe.
    """

    DEFAULT_CSS = tokenised("""
    AccountBar {
        dock: top;
        width: 100%;
        height: 1;
        background: $surface;
        color: $text;
        padding: $cadrumo-space-0 $cadrumo-gutter;
    }
    """)

    def __init__(self, *, id: str | None = None) -> None:
        """Create an empty bar; its line is written once it is mounted."""
        super().__init__("", id=id, markup=False)

    def on_mount(self) -> None:
        """Write the line in the language now on screen."""
        self.refresh_copy()

    def refresh_copy(self) -> None:
        """Re-read the session from the root and rewrite the line."""
        app = self.app
        session = app.account_session if isinstance(app, TuiAccountHostV1) else None
        self.update(account_status_line(session))


class AccountChromeScreen(Screen[None]):
    """A workbench destination: the account bar above it, the key footer below.

    The chrome is mounted from a decorated ``Mount`` handler rather than an
    ``on_mount`` method, so it runs alongside -- not instead of -- whatever
    ``on_mount`` a destination defines, sync or async, and a destination gets
    its chrome without composing it itself. A destination that already
    composes a footer keeps that one.

    Two widgets docked to the same edge share its first row, so the
    destination's own banner is pushed one row down to sit beneath the bar:
    the bar is the application's, the banner is this screen's title.
    """

    SCOPED_CSS: ClassVar[bool] = False
    DEFAULT_CSS: ClassVar[str] = """
    AccountChromeScreen .cadrumo-banner { margin-top: 1; }
    """

    @on(events.Mount)
    def _mount_account_chrome(self) -> None:
        """Add the account bar and, where missing, the key footer."""
        self.mount(AccountBar(id="account-bar"), before=0)
        # Compact, so every account key still fits an eighty-column terminal.
        footers = self.query(Footer)
        if footers:
            for footer in footers:
                footer.compact = True
        else:
            self.mount(Footer(compact=True))
        self._describe_own_appearance_key()

    def refresh_account_chrome(self) -> None:
        """Rewrite the account chrome after this page changed its language.

        The root's own key descriptions are rewritten too; they are shown in
        this page's footer, and would otherwise stay in the old language until
        the operator returned to Home.
        """
        app = self.app
        if isinstance(app, TuiAccountHostV1):
            app.refresh_account_chrome()
        else:
            for bar in self.query(AccountBar):
                bar.refresh_copy()
        self._describe_own_appearance_key()

    def _describe_own_appearance_key(self) -> None:
        """Make this screen's own appearance key agree with the root's.

        A destination binds the key itself so that a standalone host, which
        has no root bindings, still offers it. Inside the workbench root that
        binding would shadow the root's described entry and put it ahead of
        the other account keys, so there it is dropped and the root's own key
        does the same work in its place. Standalone, it is described instead.
        Entries are replaced by assignment for the reason
        ``ProfileManagerScreen._offer_language_in_footer`` gives.
        """
        bindings = self._bindings.key_to_bindings.get(_APPEARANCE_KEY)
        if not bindings:
            return
        if isinstance(self.app, TuiAccountHostV1):
            self._bindings.key_to_bindings = {
                key: entries for key, entries in self._bindings.key_to_bindings.items() if key != _APPEARANCE_KEY
            }
            self.refresh_bindings()
            return
        label = account_action_label(AccountActionV1.APPEARANCE)
        self._bindings.key_to_bindings[_APPEARANCE_KEY] = [
            replace(binding, description=label, show=True) for binding in bindings
        ]
        self.refresh_bindings()


__all__ = [
    "AccountActionV1",
    "AccountBar",
    "AccountChromeScreen",
    "TuiAccountHostV1",
    "account_action_help",
    "account_action_label",
    "account_key_label",
    "account_status_line",
]
