"""Read-only filing submission helpers.

The :class:`SubmissionEngine` runs preflight and reads historical
records only. AEAT remote submission and write-shaped portal walks are
permanently forbidden; transport methods reject immediately with
:class:`LiveSubmitForbiddenError`.

Public API discipline: callers outside this subpackage must import
only from :mod:`aeat.adapters.outbound.aeat.export` (the package root); the underscored
submodules are implementation detail.

See ``[[2026-04-12-submission-engine-research]]`` and
``[[2026-04-12-submission-engine-adr]]`` for the architectural
context.
"""

from __future__ import annotations

from ._engine import SubmissionEngine
from ._errors import (
    LiveSubmitForbiddenError,
    SubmissionError,
    SubmissionPreflightError,
)
from ._models import (
    SubmissionAttempt,
    SubmissionStatus,
    SubmittedFiling,
    make_submission_id,
)
from ._preflight import Preflight
from ._protocols import (
    AuthProviderDescription,
    AuthProviderKind,
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
    "LiveSubmitForbiddenError",
    "ModeloIdentifier",
    "Preflight",
    "SubmissionAttempt",
    "SubmissionEngine",
    "SubmissionError",
    "SubmissionPreflightError",
    "SubmissionStatus",
    "SubmittedFiling",
    "make_submission_id",
]
