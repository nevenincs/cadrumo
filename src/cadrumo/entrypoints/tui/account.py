"""Account controls and their caller-supplied screen factories.

The workbench treats Profile as an account destination and exposes the other
account utilities from its identity control.  Their visual and application
owners already exist: this module only binds those owners to caller-supplied
doors.  In particular, it neither reads profile storage nor creates an
alternative credential, language, appearance, or sign-out screen.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum, auto
from functools import partial
from typing import TYPE_CHECKING, ClassVar, override

from textual.command import DiscoveryHit, Hit, Hits, Provider

from ...core.errors.hierarchy import CadrumoError
from .components.account_chrome import AccountActionV1, TuiAccountHostV1, account_action_help, account_action_label
from .navigation import TuiScreenContextV1
from .profile.overview import ProfileManagerScreen
from .secret.login import LoginScreen
from .secret.passphrase import PassphraseScreen

if TYPE_CHECKING:
    from textual.app import App
    from textual.screen import Screen

    from ...application.overview.home import HomeAccountSession
    from .operations.controller_port import OperationControllerPort


type AccountProfileFactoryV1 = Callable[[TuiScreenContextV1], ProfileManagerScreen]
type AccountChangeUserFactoryV1 = Callable[[], LoginScreen | AccountDirectSessionActionV1]
type AccountPasswordFactoryV1 = Callable[[], PassphraseScreen]
type AccountAccessFactoryV1 = Callable[[], Screen[None]]
type AccountAppearanceFactoryV1 = Callable[[App[AccountRecomposeRequiredV1 | None]], str]
type AccountLanguageFactoryV1 = Callable[[ProfileManagerScreen], None]
type AccountSignOutFactoryV1 = Callable[[], Awaitable[OperationControllerPort] | AccountDirectSessionActionV1]
type AccountSessionReaderV1 = Callable[[], Awaitable[HomeAccountSession]]


class AccountSessionExpiredError(CadrumoError):
    """Signal that the current non-secret account session must be recomposed."""


class AccountRecomposeReasonV1(StrEnum):
    """Why the current profile-bound workbench must be discarded."""

    CHANGE_USER = "change_user"
    PASSWORD_CHANGED = auto()
    SIGNED_OUT = "signed_out"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class AccountRecomposeRequiredV1:
    """Non-secret handoff asking the outer bootstrap owner for a fresh root."""

    reason: AccountRecomposeReasonV1
    profile_id: str | None = None
    profile_label: str | None = None

    def __post_init__(self) -> None:
        """Keep handover identity complete and prohibit it on close outcomes."""
        has_profile = self.profile_id is not None or self.profile_label is not None
        if self.reason is AccountRecomposeReasonV1.CHANGE_USER:
            if (self.profile_id is None) != (self.profile_label is None):
                raise ValueError("change-user recomposition requires both profile identity fields or neither")
            if has_profile and (not self.profile_id or not self.profile_label):
                raise ValueError("change-user profile identity fields must not be empty")
            return
        if has_profile:
            raise ValueError("closed-session recomposition cannot retain a profile identity")


@dataclass(frozen=True, slots=True)
class AccountDirectSessionActionV1:
    """A runtime-owned account effect completed after the old root is severed."""

    complete: Callable[[], Awaitable[AccountRecomposeRequiredV1]]


@dataclass(frozen=True, slots=True)
class AccountFactoriesV1:
    """The production account utilities, each delegated to its existing owner."""

    profile: AccountProfileFactoryV1
    change_user: AccountChangeUserFactoryV1
    password: AccountPasswordFactoryV1 | None
    appearance: AccountAppearanceFactoryV1
    language: AccountLanguageFactoryV1
    sign_out: AccountSignOutFactoryV1
    access: AccountAccessFactoryV1 | None = None
    onboarding_pending: bool = False
    """Whether the profile still needs setup, so the session opens on the setup walk."""


class WorkbenchAccountProviderV1(Provider):
    """Offer the account controls in the command palette.

    The controls sit on the root shell, which every destination screen covers,
    so without this the palette was the one cross-screen surface that could not
    reach them. Entries exist only while the session has account doors;
    offering a control that can only refuse would be a false promise.
    Appearance is left to the root's system commands, which offer it with or
    without a profile, so it is not listed twice.
    """

    _ACTIONS: ClassVar[tuple[AccountActionV1, ...]] = tuple(
        action for action in AccountActionV1 if action is not AccountActionV1.APPEARANCE
    )

    def _host(self) -> TuiAccountHostV1 | None:
        app = self.app
        if isinstance(app, TuiAccountHostV1) and app.account_actions_available:
            return app
        return None

    @override
    async def search(self, query: str) -> Hits:
        """Fuzzy-match the account controls by their on-screen names."""
        host = self._host()
        if host is None:
            return
        matcher = self.matcher(query)
        for action in self._ACTIONS:
            if not host.account_action_available(action):
                continue
            text = account_action_label(action)
            if (score := matcher.match(text)) > 0:
                yield Hit(
                    score=score,
                    match_display=matcher.highlight(text),
                    command=partial(host.run_account_action, action),
                    text=text,
                    help=account_action_help(action),
                )

    @override
    async def discover(self) -> Hits:
        """List the account controls before anything is typed."""
        host = self._host()
        if host is None:
            return
        for action in self._ACTIONS:
            if not host.account_action_available(action):
                continue
            text = account_action_label(action)
            yield DiscoveryHit(
                display=text,
                command=partial(host.run_account_action, action),
                text=text,
                help=account_action_help(action),
            )


__all__ = [
    "AccountAccessFactoryV1",
    "AccountAppearanceFactoryV1",
    "AccountChangeUserFactoryV1",
    "AccountDirectSessionActionV1",
    "AccountFactoriesV1",
    "AccountLanguageFactoryV1",
    "AccountPasswordFactoryV1",
    "AccountProfileFactoryV1",
    "AccountRecomposeReasonV1",
    "AccountRecomposeRequiredV1",
    "AccountSessionExpiredError",
    "AccountSignOutFactoryV1",
    "WorkbenchAccountProviderV1",
]
