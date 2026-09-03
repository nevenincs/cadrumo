"""Production composition for the account utilities.

The workbench treats Profile as an account destination and exposes the other
account utilities from its identity control.  Their visual and application
owners already exist: this module only binds those owners to caller-supplied
doors.  In particular, it neither reads profile storage nor creates an
alternative credential, language, appearance, or sign-out screen.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from textual.app import App

from .components.theme import toggle_appearance
from .navigation import TuiScreenContextV1
from .profile.overview import ProfileManagerScreen
from .secret.login import LoginScreen
from .secret.passphrase import PassphraseChangeAttempt, PassphraseScreen

if TYPE_CHECKING:
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
type AccountAppearanceFactoryV1 = Callable[[App[None]], str]
type AccountLanguageFactoryV1 = Callable[[ProfileManagerScreen], None]
type AccountSignOutFactoryV1 = Callable[[], Awaitable[OperationController]]


class AccountRecomposeReasonV1(StrEnum):
    """Why the current profile-bound workbench must be discarded."""

    CHANGE_USER = "change_user"
    PASSWORD_CHANGED = "password_changed"  # noqa: S105 - stable non-secret lifecycle token
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
    persist_profile_field: Callable[[str, str], ProfileOverview],
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
            validate=validate_profile_field,
            launch_source=launch_profile_source,
            credential_postures=credential_postures,
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

    The returned door submits only when invoked.  Starting and observing stay
    with the existing operation modal, so composition performs no operation,
    persistence, or credential work.
    """
    from ...application.user_profile.operations import build_profile_logout_operation_request
    from .operations.controller import OperationController

    parsed_profile_id = UUID(profile_id)

    async def sign_out() -> OperationController:
        submission = await services.submission.submit(
            build_profile_logout_operation_request(parsed_profile_id),
            actor_ref=actor_ref,
        )
        return OperationController(services=services, submission=submission, actor_ref=actor_ref)

    return sign_out


__all__ = [
    "AccountAppearanceFactoryV1",
    "AccountChangeUserFactoryV1",
    "AccountFactoriesV1",
    "AccountLanguageFactoryV1",
    "AccountPasswordFactoryV1",
    "AccountProfileFactoryV1",
    "AccountRecomposeReasonV1",
    "AccountRecomposeRequiredV1",
    "AccountSignOutFactoryV1",
    "compose_account_factories",
    "compose_profile_sign_out_factory",
]
