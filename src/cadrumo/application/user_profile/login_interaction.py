"""Frontend-neutral interaction contract for selecting and unlocking a profile."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from ...core.profile_discovery import ProfileSummaryOutcome
from .login_session import ProfileLoginOutcome, login_profile, resolve_login_target
from .profile_summary import ProfileSummaryInventory, summary_inventory

if TYPE_CHECKING:
    from collections.abc import Callable

    from ...domain.calculations.registry.authority_artifact import ProfileDecodeContext


@dataclass(frozen=True, slots=True)
class ProfileLoginChoice:
    """One committed profile available to an authentication chooser."""

    profile_id: str
    label: str


@dataclass(frozen=True, slots=True)
class ProfileLoginAttempt:
    """A completed login operation represented without frontend exceptions."""

    outcome: ProfileLoginOutcome | None = None
    refusal: str | None = None


class ProfileLoginInventoryState(StrEnum):
    """Truthful result of the non-authenticating profile inventory read.

    A surface that offers a sign-in must know which of four situations it is
    in, and the difference matters to the operator in each case. An inventory
    that could not be read is NOT an empty one: reporting a degraded store as
    "no profiles yet" invites the operator to create a second profile beside
    the one the reader failed to see.
    """

    RECOGNIZED = "recognized"
    """The store was read and offers at least one profile to sign into."""

    CONCURRENT_CHANGE = "concurrent_change"
    """The store changed underneath the read; nothing is offered."""

    DEGRADED = "degraded"
    """The store could not be read truthfully; nothing is offered."""

    EMPTY = "empty"
    """The store was read and holds no profile; registration is the next step."""


@dataclass(frozen=True, slots=True)
class ProfileLoginInventoryV1:
    """One immutable inventory observation, carrying no credential material.

    ``reason_code`` is present exactly on the two unavailable states and names
    the condition for an operator-facing report. ``choices`` and
    ``preselected_profile_id`` are populated only when the inventory is
    recognized, so a caller cannot offer a sign-in the store does not support.
    """

    state: ProfileLoginInventoryState
    choices: tuple[ProfileLoginChoice, ...] = field(default=(), repr=False)
    preselected_profile_id: str | None = field(default=None, repr=False)
    reason_code: str | None = None

    def __post_init__(self) -> None:
        """Refuse a contradictory combination of state, choices, and reason."""
        identifiers = tuple(choice.profile_id for choice in self.choices)
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("profile login inventory choices must each name one profile once")
        if self.state is ProfileLoginInventoryState.RECOGNIZED:
            if not self.choices or self.reason_code is not None:
                raise ValueError("a recognized profile inventory carries choices and no reason code")
        elif self.choices or self.preselected_profile_id is not None:
            raise ValueError("an unavailable or empty profile inventory cannot carry login choices")
        unavailable = self.state in {
            ProfileLoginInventoryState.CONCURRENT_CHANGE,
            ProfileLoginInventoryState.DEGRADED,
        }
        if unavailable != (self.reason_code is not None):
            raise ValueError("a reason code names an unavailable inventory and nothing else")
        if self.preselected_profile_id is not None and self.preselected_profile_id not in identifiers:
            raise ValueError("the preselected profile is absent from the recognized choices")


def profile_login_choices() -> tuple[ProfileLoginChoice, ...]:
    """Return committed profiles in the stable chooser order."""
    from ..workflow.profile_bucket_scan import list_profile_buckets

    return tuple(
        ProfileLoginChoice(profile_id=pointer.bucket_id, label=pointer.label)
        for pointer in sorted(list_profile_buckets().values(), key=lambda pointer: pointer.label.casefold())
    )


def preselected_profile_login_id(name: str | None) -> str | None:
    """Resolve the profile an authentication chooser should open on."""
    from ...core.bucket_pointer import resolve_active_bucket_id

    if name is None:
        return resolve_active_bucket_id()
    return resolve_login_target(name).bucket_id


def observe_profile_login_inventory(
    *,
    inventory_reader: Callable[[], ProfileSummaryInventory] = summary_inventory,
    choice_reader: Callable[[], tuple[ProfileLoginChoice, ...]] = profile_login_choices,
    preselection_reader: Callable[[str | None], str | None] = preselected_profile_login_id,
) -> ProfileLoginInventoryV1:
    """Read which profiles can be signed into, without unlocking any of them.

    This observation authenticates nothing and opens no custody session. It is
    the question every sign-in surface asks first, and it is kept apart from
    admission on purpose: whether the store can be read is a different fact
    from whether a particular profile can be unlocked, and a surface that
    conflated them reported a locked profile as a missing one.

    The choices are re-read against the same inventory rather than trusted,
    because the two reads can straddle a concurrent registration or deletion.
    A disagreement is reported as degraded rather than resolved by preferring
    one of them.
    """
    inventory = inventory_reader()
    if inventory.outcome is ProfileSummaryOutcome.CONCURRENT_CHANGE:
        return ProfileLoginInventoryV1(
            state=ProfileLoginInventoryState.CONCURRENT_CHANGE,
            reason_code="profile.inventory.concurrent_change",
        )
    if not inventory.recognized:
        return ProfileLoginInventoryV1(
            state=ProfileLoginInventoryState.DEGRADED,
            reason_code="profile.inventory.unavailable",
        )
    if not inventory.summaries:
        return ProfileLoginInventoryV1(state=ProfileLoginInventoryState.EMPTY)

    choices = choice_reader()
    expected = {str(item.profile_id): str(item.label) for item in inventory.summaries}
    observed = {choice.profile_id: choice.label for choice in choices}
    if len(choices) != len(inventory.summaries) or expected != observed:
        return ProfileLoginInventoryV1(
            state=ProfileLoginInventoryState.DEGRADED,
            reason_code="profile.inventory.changed",
        )
    preselected = preselection_reader(None)
    if preselected not in observed:
        preselected = None
    return ProfileLoginInventoryV1(
        state=ProfileLoginInventoryState.RECOGNIZED,
        choices=choices,
        preselected_profile_id=preselected,
    )


def attempt_profile_login(
    profile_id: str,
    passphrase: str,
    *,
    profile_decode_context: ProfileDecodeContext,
) -> ProfileLoginAttempt:
    """Unlock a chosen profile under the caller's pinned schema context.

    The credential screen is deliberately frontend-neutral, so it receives the
    decode context that the workflow owner already pinned.  Opening an
    authority here would allow the screen to authenticate against a different
    generation from the surrounding bootstrap/session composition.
    """
    from ...core.errors.error_codes import resolve_error_message
    from ...domain.user_profile.errors import ProfileNotFoundError
    from .authentication import ProfileAuthenticationRefusedError
    from .login_session import ProfileLoginThrottledError

    try:
        outcome = login_profile(
            name=profile_id,
            passphrase_callback=lambda: passphrase,
            profile_decode_context=profile_decode_context,
        )
    except (ProfileAuthenticationRefusedError, ProfileLoginThrottledError, ProfileNotFoundError) as refusal:
        return ProfileLoginAttempt(refusal=resolve_error_message(refusal))
    return ProfileLoginAttempt(outcome=outcome)


__all__ = [
    "ProfileLoginAttempt",
    "ProfileLoginChoice",
    "ProfileLoginInventoryState",
    "ProfileLoginInventoryV1",
    "attempt_profile_login",
    "observe_profile_login_inventory",
    "preselected_profile_login_id",
    "profile_login_choices",
]
