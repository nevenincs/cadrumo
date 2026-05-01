"""Submission lifecycle protocols live in :mod:`aeat.domain.submission`."""

from __future__ import annotations

from .....application.auth import AuthProviderDescription, AuthProviderKind
from .....domain.submission._protocols import (
    AuthProviderProbe,
    DeadlineWindowChecker,
    DraftLoader,
    DraftStatus,
    FilingDraftLike,
    FilingFinding,
    FilingFindingSeverity,
    ModeloIdentifier,
)

__all__ = [
    "AuthProviderDescription",
    "AuthProviderKind",
    "AuthProviderProbe",
    "DeadlineWindowChecker",
    "DraftLoader",
    "DraftStatus",
    "FilingDraftLike",
    "FilingFinding",
    "FilingFindingSeverity",
    "ModeloIdentifier",
]
