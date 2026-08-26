"""The known explicit profile acquisition sources: what exists, never how to run it.

Every operator-facing surface offering a "get data" launch action reads this
catalogue rather than hand-listing sources, so a new acquisition source is
declared once. This module is deliberately thin: it names the sources that
exist. It resolves no capability, scope, or authentication posture -- no
public contract for that currently exists (tracked separately) -- and it
submits nothing: a launch is always the caller's own composed operation
door. Operator-facing copy is a presentation concern and is resolved by the
adapter rendering the source, not declared here.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from ...core import STRICT_FROZEN_CONFIG

__all__ = [
    "ProfileAcquisitionSourceKey",
    "ProfileAcquisitionSourceV1",
    "known_profile_acquisition_sources",
]


class ProfileAcquisitionSourceKey(StrEnum):
    """Every acquisition source an operator may explicitly launch from a profile."""

    CENSAL_REVIEW = "censal_review"
    FILED_HISTORY = "filed_history"


class ProfileAcquisitionSourceV1(BaseModel):
    """One acquisition source's identity, never resolved prose."""

    model_config = STRICT_FROZEN_CONFIG

    key: ProfileAcquisitionSourceKey


_KNOWN_SOURCES: tuple[ProfileAcquisitionSourceV1, ...] = (
    ProfileAcquisitionSourceV1(key=ProfileAcquisitionSourceKey.CENSAL_REVIEW),
    ProfileAcquisitionSourceV1(key=ProfileAcquisitionSourceKey.FILED_HISTORY),
)


def known_profile_acquisition_sources() -> tuple[ProfileAcquisitionSourceV1, ...]:
    """Return every declared acquisition source, in a stable declaration order."""
    return _KNOWN_SOURCES
