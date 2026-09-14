"""Frontend-neutral interaction contract for selecting and unlocking a profile."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .login_session import ProfileLoginOutcome, login_profile, resolve_login_target

if TYPE_CHECKING:
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
    "attempt_profile_login",
    "preselected_profile_login_id",
    "profile_login_choices",
]
