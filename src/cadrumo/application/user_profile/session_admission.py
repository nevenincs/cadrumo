"""Admit explicit local custody without reading or mutating shared sign-in receipts.

Runtime clients own automatic proof presentation. This local composition door
can reuse custody already bound by its owner or accept an explicit credential
journey; it cannot unwrap a persisted receipt in a frontend process.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

from ...core.errors.hierarchy import InternalInvariantError
from ...core.profile_session import ProfileSessionRefusalReason
from .login_session import ProfileLoginOutcome
from .login_session_port import profile_current_bucket_session, profile_session_serves_bucket

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority_artifact import ProfileDecodeContext


class ProfileSessionAdmissionState(StrEnum):
    """Closed set of outcomes for one attempt to admit a profile session.

    The three admitting states are kept apart rather than collapsed into a
    boolean because they carry different obligations. A reused or resumed
    session costs the operator nothing and needs no notice; an authenticated
    one may be process-scoped and owes them that fact.

    The two refusing states are likewise distinct. ``CREDENTIALS_REQUIRED``
    means nobody was available to ask -- a non-interactive invocation with no
    secret channel -- and is a refusal about the CALLER. ``DECLINED`` means the
    operator was asked and chose not to authenticate, which is an ordinary
    outcome and not an error.
    """

    ALREADY_ADMITTED = "already_admitted"
    """A live session in this process already served the requested profile."""

    RESUMED = "resumed"
    """The persisted acceleration receipt served, with no credential prompt."""

    AUTHENTICATED = "authenticated"
    """The supplied credential journey authenticated the profile."""

    CREDENTIALS_REQUIRED = "credentials_required"
    """No session could be resumed and no credential journey was offered."""

    DECLINED = "declined"
    """The credential journey ran and the operator did not authenticate."""


@dataclass(frozen=True, slots=True)
class ProfileCredentialRequestV1:
    """What a credential journey is told before it asks the operator.

    ``resume_refusal`` is passed deliberately: a journey that wants to explain
    WHY credentials are needed -- an expired session reads differently from a
    never-logged-in one -- has the typed reason rather than having to re-derive
    it, and a journey that does not care may ignore it.
    """

    bucket_id: str | None
    profile_decode_context: ProfileDecodeContext
    resume_refusal: ProfileSessionRefusalReason | None


class ProfileCredentialJourneyV1(Protocol):
    """The surface-owned half of admission: obtain credentials and authenticate.

    A journey returns the login outcome it achieved, or ``None`` when the
    operator declined. It authenticates an invocation target through
    ``authenticate_profile_for_invocation`` so that password proof, throttling
    and local custody binding remain owned by the login service. Shared human
    sign-in and profile selection belong to their runtime boundaries.
    """

    def __call__(self, request: ProfileCredentialRequestV1, /) -> ProfileLoginOutcome | None:
        """Authenticate the requested profile, or return ``None`` if declined."""
        ...


@dataclass(frozen=True, slots=True)
class ProfileSessionAdmissionV1:
    """One closed, non-secret account of an admission attempt."""

    state: ProfileSessionAdmissionState
    bucket_id: str | None
    outcome: ProfileLoginOutcome | None = None
    resume_refusal: ProfileSessionRefusalReason | None = None

    @property
    def admitted(self) -> bool:
        """Whether a live session now serves :attr:`bucket_id`."""
        return self.state in {
            ProfileSessionAdmissionState.ALREADY_ADMITTED,
            ProfileSessionAdmissionState.RESUMED,
            ProfileSessionAdmissionState.AUTHENTICATED,
        }


def admit_profile_session(
    *,
    bucket_id: str | None,
    profile_decode_context: ProfileDecodeContext,
    credentials: ProfileCredentialJourneyV1 | None = None,
    now: datetime | None = None,
) -> ProfileSessionAdmissionV1:
    """Reuse owner-bound custody or require an explicit credential journey.

    The requested profile is revalidated after the journey. Receipt admission
    belongs to the native runtime transport, never this in-process helper.
    """
    if bucket_id is not None and profile_session_serves_bucket(profile_current_bucket_session(), bucket_id):
        return ProfileSessionAdmissionV1(
            state=ProfileSessionAdmissionState.ALREADY_ADMITTED,
            bucket_id=bucket_id,
        )
    # No receipt was observed. Do not report absent, expired, or keyring
    # unavailable merely because local custody is not bound.
    refusal = None

    if credentials is None:
        return ProfileSessionAdmissionV1(
            state=ProfileSessionAdmissionState.CREDENTIALS_REQUIRED,
            bucket_id=bucket_id,
            resume_refusal=refusal,
        )

    outcome = credentials(
        ProfileCredentialRequestV1(
            bucket_id=bucket_id,
            profile_decode_context=profile_decode_context,
            resume_refusal=refusal,
        )
    )
    if outcome is None:
        return ProfileSessionAdmissionV1(
            state=ProfileSessionAdmissionState.DECLINED,
            bucket_id=bucket_id,
            resume_refusal=refusal,
        )
    if bucket_id is not None and outcome.bucket_id != bucket_id:
        raise InternalInvariantError("credential journey authenticated a different profile from the requested target")
    _require_admitted_session(outcome.bucket_id, origin="credential journey")
    return ProfileSessionAdmissionV1(
        state=ProfileSessionAdmissionState.AUTHENTICATED,
        bucket_id=outcome.bucket_id,
        outcome=outcome,
        resume_refusal=refusal,
    )


def _require_admitted_session(bucket_id: str, *, origin: str) -> None:
    """Refuse to report an admission the live binding does not support."""
    if not profile_session_serves_bucket(profile_current_bucket_session(), bucket_id):
        raise InternalInvariantError(f"{origin} did not leave a live session serving the admitted profile")


__all__ = [
    "ProfileCredentialJourneyV1",
    "ProfileCredentialRequestV1",
    "ProfileSessionAdmissionState",
    "ProfileSessionAdmissionV1",
    "admit_profile_session",
]
