"""The known explicit profile acquisition sources: what exists, never how to run it.

Every operator-facing surface offering a "get data" launch action reads this
catalogue rather than hand-listing sources, so a new acquisition source is
declared once. It submits nothing: a launch is always the caller's own
composed operation door. Operator-facing copy is a presentation concern and
is resolved by the adapter rendering the source, not declared here.

Credential posture is the one exception: whether a source needs a held AEAT
credential to run, and whether the operator currently has one on file, are
facts an operator needs BEFORE pressing launch, so this module also declares
that contract -- derived from the real owning authority
(:class:`~cadrumo.application.auth.models.AuthState`), never a
presentation-local guess. Both currently declared sources
(:mod:`~cadrumo.application.live.censo`,
:mod:`~cadrumo.application.live.filed_data_capture`) route through
:func:`~cadrumo.application.live.session.active_verified_session`, the shared
AEAT live-read gate, so both require the same posture; a source that read
only locally-held facts would declare `requires_aeat_authentication=False`.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel

from ...core.models import STRICT_FROZEN_CONFIG

if TYPE_CHECKING:
    from ..auth.models import AuthState

__all__ = [
    "AcquisitionSourceCredentialPostureV1",
    "ProfileAcquisitionSourceKey",
    "ProfileAcquisitionSourceV1",
    "known_profile_acquisition_sources",
    "resolve_acquisition_source_credential_postures",
]


class ProfileAcquisitionSourceKey(StrEnum):
    """Every acquisition source an operator may explicitly launch from a profile."""

    CENSAL_REVIEW = "censal_review"
    FILED_HISTORY = "filed_history"


class ProfileAcquisitionSourceV1(BaseModel):
    """One acquisition source's identity, never resolved prose.

    ``requires_aeat_authentication`` is read from the source's own
    implementation, not asserted for presentation convenience: both
    declared sources call :func:`~cadrumo.application.live.session
    .active_verified_session` before touching AEAT, so both are `True`
    today. A future source resolving only already-held local facts would
    declare `False` here rather than inheriting a blanket default.
    """

    model_config = STRICT_FROZEN_CONFIG

    key: ProfileAcquisitionSourceKey
    requires_aeat_authentication: bool


_KNOWN_SOURCES: tuple[ProfileAcquisitionSourceV1, ...] = (
    ProfileAcquisitionSourceV1(key=ProfileAcquisitionSourceKey.CENSAL_REVIEW, requires_aeat_authentication=True),
    ProfileAcquisitionSourceV1(key=ProfileAcquisitionSourceKey.FILED_HISTORY, requires_aeat_authentication=True),
)


def known_profile_acquisition_sources() -> tuple[ProfileAcquisitionSourceV1, ...]:
    """Return every declared acquisition source, in a stable declaration order."""
    return _KNOWN_SOURCES


class AcquisitionSourceCredentialPostureV1(BaseModel):
    """Whether one source's declared authentication requirement is currently met.

    ``credential_held`` and ``provider_id`` are read straight from
    :class:`~cadrumo.application.auth.models.AuthState` -- the same
    persisted workflow-state fact the status page and every auth CLI
    surface already read. This model states only what the source needs
    and what is on file; it does not claim the on-file credential is
    still valid against AEAT right now, which only a live probe can know.
    """

    model_config = STRICT_FROZEN_CONFIG

    source: ProfileAcquisitionSourceKey
    requires_aeat_authentication: bool
    credential_held: bool
    provider_id: str | None


def resolve_acquisition_source_credential_postures(
    auth: AuthState,
) -> tuple[AcquisitionSourceCredentialPostureV1, ...]:
    """Derive every declared source's credential posture from real auth state.

    Pure: reads only the supplied :class:`AuthState`. A source that does
    not require AEAT authentication always reports `credential_held=True`
    -- there is nothing to hold.
    """
    held = auth.provider is not None and auth.authenticated_at is not None
    return tuple(
        AcquisitionSourceCredentialPostureV1(
            source=source.key,
            requires_aeat_authentication=source.requires_aeat_authentication,
            credential_held=held if source.requires_aeat_authentication else True,
            provider_id=auth.provider if source.requires_aeat_authentication else None,
        )
        for source in _KNOWN_SOURCES
    )
