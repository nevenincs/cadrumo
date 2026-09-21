"""Production composition for the account utilities.

The workbench treats Profile as an account destination and exposes the other
account utilities from its identity control.  Their visual and application
owners already exist: this module only binds those owners to caller-supplied
doors.  In particular, it neither reads profile storage nor creates an
alternative credential, language, appearance, or sign-out screen.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum, auto
from functools import partial
from typing import TYPE_CHECKING, ClassVar, override
from uuid import UUID

from textual.command import DiscoveryHit, Hit, Hits, Provider

from ...core.errors.hierarchy import CadrumoError
from .components.account_chrome import AccountActionV1, TuiAccountHostV1, account_action_help, account_action_label
from .components.theme import AppearanceHost, toggle_appearance
from .navigation import TuiScreenContextV1
from .profile.overview import ProfileManagerScreen
from .secret.login import LoginScreen
from .secret.passphrase import PassphraseChangeAttempt, PassphraseScreen

if TYPE_CHECKING:
    from textual.screen import Screen

    from ...application.operations.composition import OperationComposedServices
    from ...application.user_profile.acquisition_sources import (
        AcquisitionSourceCredentialPostureV1,
        ProfileAcquisitionSourceV1,
    )
    from ...application.user_profile.login_interaction import ProfileLoginAttempt, ProfileLoginChoice
    from ...application.user_profile.overview import ProfileOverview
    from ...core.credentials import ProfilePasswordAssessment
    from .operations.controller import OperationController


type AccountProfileFactoryV1 = Callable[[TuiScreenContextV1], ProfileManagerScreen]
type AccountChangeUserFactoryV1 = Callable[[], LoginScreen]
type AccountPasswordFactoryV1 = Callable[[], PassphraseScreen]
type AccountAppearanceFactoryV1 = Callable[[AppearanceHost], str]
type AccountLanguageFactoryV1 = Callable[[ProfileManagerScreen], None]
type AccountSignOutFactoryV1 = Callable[[], Awaitable[OperationController]]


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
            if not self.profile_id or not self.profile_label:
                raise ValueError("change-user recomposition requires the authenticated profile identity")
            return
        if has_profile:
            raise ValueError("closed-session recomposition cannot retain a profile identity")


@dataclass(frozen=True, slots=True)
class AccountFactoriesV1:
    """The production account utilities, each delegated to its existing owner."""

    profile: AccountProfileFactoryV1
    change_user: AccountChangeUserFactoryV1
    password: AccountPasswordFactoryV1
    appearance: AccountAppearanceFactoryV1
    language: AccountLanguageFactoryV1
    sign_out: AccountSignOutFactoryV1


def compose_account_factories(
    *,
    profile_overview: ProfileOverview,
    persist_profile_field: Callable[[str, str, int, str], ProfileOverview],
    add_profile_row: Callable[[str, Mapping[str, str], int, str], ProfileOverview] | None = None,
    update_profile_row: Callable[[str, str, Mapping[str, str], Sequence[str], int, str], ProfileOverview] | None = None,
    remove_profile_row: Callable[[str, str, int, str], ProfileOverview] | None = None,
    login_choices: Sequence[ProfileLoginChoice],
    authenticate: Callable[[str, str], ProfileLoginAttempt],
    assess_password: Callable[[str], ProfilePasswordAssessment],
    rotate_password: Callable[[str, str, str], PassphraseChangeAttempt],
    sign_out: AccountSignOutFactoryV1,
    preselected_profile_id: str | None = None,
    validate_profile_field: Callable[[str, str], str | None] | None = None,
    launch_profile_source: Callable[[ProfileAcquisitionSourceV1], Awaitable[None]] | None = None,
    credential_postures: Sequence[AcquisitionSourceCredentialPostureV1] | None = None,
    appearance: AccountAppearanceFactoryV1 = toggle_appearance,
    complete_setup: Callable[[], ProfileOverview] | None = None,
    open_document_reader: Callable[[], Screen[None]] | None = None,
) -> AccountFactoriesV1:
    """Bind already-composed account doors to their canonical TUI owners.

    Every value and effect door is supplied by the installed host.  This makes
    composition explicit: constructing a factory does not read storage,
    unlock a profile, mutate settings, or submit the strong-close operation.
    """

    def profile(context: TuiScreenContextV1) -> ProfileManagerScreen:
        """Create the sole Profile destination for its admitted route."""
        if context.destination != "workbench.profile":
            raise ValueError("the account Profile factory accepts only the Profile destination")
        return ProfileManagerScreen(
            profile_overview,
            persist=persist_profile_field,
            add_row=add_profile_row,
            update_row=update_profile_row,
            remove_row=remove_profile_row,
            complete_setup=complete_setup,
            validate=validate_profile_field,
            launch_source=launch_profile_source,
            credential_postures=credential_postures,
            open_document_reader=open_document_reader,
        )

    def change_user() -> LoginScreen:
        """Create the existing credential screen for a deliberate handover."""
        return LoginScreen(
            choices=login_choices,
            authenticate=authenticate,
            preselected=preselected_profile_id,
        )

    def password() -> PassphraseScreen:
        """Create the existing passphrase-rotation screen."""
        return PassphraseScreen(assess=assess_password, rotate=rotate_password)

    def language(screen: ProfileManagerScreen) -> None:
        """Open the Profile owner's existing language chooser, not a copy."""
        screen.action_choose_language()

    return AccountFactoriesV1(
        profile=profile,
        change_user=change_user,
        password=password,
        appearance=appearance,
        language=language,
        sign_out=sign_out,
    )


def compose_profile_sign_out_factory(
    services: OperationComposedServices,
    *,
    profile_id: str,
    actor_ref: str = "operator:tui-account",
) -> AccountSignOutFactoryV1:
    """Bind the canonical strong-close operation to the current profile.

    The returned door submits and starts the close only when invoked, exactly
    as ``config logout`` does; composition performs no operation, persistence,
    or credential work. Observation stays with the operation modal, which
    watches and never starts: a close that was submitted but not started sat
    in its created state indefinitely while the modal reported it in progress.
    """
    from ...application.user_profile.operations import build_profile_logout_operation_request
    from .operations.controller import OperationController

    parsed_profile_id = UUID(profile_id)

    async def sign_out() -> OperationController:
        submission = await services.submission.submit(
            build_profile_logout_operation_request(parsed_profile_id),
            actor_ref=actor_ref,
        )
        controller = OperationController(services=services, submission=submission, actor_ref=actor_ref)
        await controller.start()
        return controller

    return sign_out


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
            text = account_action_label(action)
            yield DiscoveryHit(
                display=text,
                command=partial(host.run_account_action, action),
                text=text,
                help=account_action_help(action),
            )


__all__ = [
    "AccountAppearanceFactoryV1",
    "AccountChangeUserFactoryV1",
    "AccountFactoriesV1",
    "AccountLanguageFactoryV1",
    "AccountPasswordFactoryV1",
    "AccountProfileFactoryV1",
    "AccountRecomposeReasonV1",
    "AccountRecomposeRequiredV1",
    "AccountSessionExpiredError",
    "AccountSignOutFactoryV1",
    "WorkbenchAccountProviderV1",
    "compose_account_factories",
    "compose_profile_sign_out_factory",
]
