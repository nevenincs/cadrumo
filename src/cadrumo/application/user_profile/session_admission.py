"""The one door that admits a profile session for use, whoever is asking.

Every surface that needs an unlocked profile wants the same sequence: reuse a
session this process already holds, else resume the acceleration receipt, else
ask the operator for credentials, and in every case prove afterwards that the
session now bound is the one that was asked for. The CLI grew that sequence
inside its own dispatch gate and the installed workbench grew a second copy in
its bootstrap, which is how the two surfaces came to disagree about what being
logged in means.

So the sequence lives here, once, and the surfaces supply only what is
genuinely theirs: how to obtain credentials from their operator. A parsed CLI
invocation reads a passphrase from a declared secret channel; the installed
workbench opens its existing Login screen. Neither decides what counts as an
admitted session, and neither may skip the proof at the end.

The door never holds session state of its own. Binding belongs to the login
services it calls, which publish process-wide through the login-session port;
this module only sequences them and reports, in typed terms, what happened.

See Also:
    :func:`~cadrumo.application.user_profile.login_session.bind_resumed_profile_session`
        The single resume authority this door consults first.
    :func:`~cadrumo.application.user_profile.login_session.authenticate_profile_for_invocation`
        The non-selecting authentication a journey uses for one invocation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

from ...core.errors.hierarchy import InternalInvariantError
from ...core.profile_session import ProfileSessionRefusalReason
from .login_session import ProfileLoginOutcome, bind_resumed_profile_session
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
    resume_refusal: ProfileSessionRefusalReason


class ProfileCredentialJourneyV1(Protocol):
    """The surface-owned half of admission: obtain credentials and authenticate.

    A journey returns the login outcome it achieved, or ``None`` when the
    operator declined. It must authenticate through a canonical login door --
    ``authenticate_profile_for_invocation`` for a target scoped to one
    invocation, ``login_profile`` when the operator is genuinely selecting a
    profile -- so that binding, throttling and handover stay owned by the
    login services rather than re-implemented per surface.
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
    """Reuse, resume, or authenticate ``bucket_id``, and prove the result.

    The order is fixed and is the whole point of the door. Reuse first,
    because a session this process already holds costs nothing and prompting
    over it would be a defect the operator sees as a second passphrase for one
    command. Resume second, because the acceleration receipt exists precisely
    to avoid the prompt. Credentials last, and only from the journey the
    caller supplied.

    The proof at the end is not a formality. Every admitting branch asserts
    that the bound session serves this exact profile, because the failure it
    catches -- a binding that did not survive the frame that made it, or an
    authentication that bound a different profile -- is silent otherwise and
    surfaces much later as an unreadable record.

    Args:
        bucket_id: The exact profile UUID to admit, already resolved -- this
            door does not interpret labels. None when the operator has not
            named a profile yet, which only a credential journey can resolve.
        profile_decode_context: The decode context of the enclosing pinned
            authority operation. Resuming or authenticating without one is
            refused by the services below; no bundled-schema fallback exists.
        credentials: The surface's credential journey, or ``None`` for a
            caller that cannot prompt.
        now: UTC evaluation instant; the canonical clock when omitted.

    Returns:
        The typed admission account, carrying the resume refusal on every
        branch that had one.

    Raises:
        InternalInvariantError: When a branch that reports an admitted session
            did not leave one bound for this exact profile.
    """
    if bucket_id is None:
        # Nothing has been named, so there is nothing to reuse or resume: an
        # acceleration receipt is addressed to one profile, and reusing
        # whichever session happened to be bound would admit a profile the
        # operator did not ask for. Only a journey can produce a target here.
        refusal = ProfileSessionRefusalReason.ABSENT
    else:
        if profile_session_serves_bucket(profile_current_bucket_session(), bucket_id):
            return ProfileSessionAdmissionV1(
                state=ProfileSessionAdmissionState.ALREADY_ADMITTED,
                bucket_id=bucket_id,
            )

        resume_refusal = bind_resumed_profile_session(
            bucket_id=bucket_id,
            now=now,
            profile_decode_context=profile_decode_context,
        )
        if resume_refusal is None:
            _require_admitted_session(bucket_id, origin="resume")
            return ProfileSessionAdmissionV1(state=ProfileSessionAdmissionState.RESUMED, bucket_id=bucket_id)
        refusal = resume_refusal

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
