"""Submission lifecycle domain package."""

from __future__ import annotations

from ._errors import LiveSubmitForbiddenError, SubmissionError, SubmissionPreflightError
from ._engine import SubmissionEngine
from ._models import SubmissionAttempt, SubmissionStatus, SubmittedFiling, make_submission_id
from ._preflight import Preflight
from ._protocols import (
    AuthProviderProbe,
    DeadlineWindowChecker,
    DraftLoader,
    DraftStatus,
    FilingDraftLike,
    FilingFinding,
    FilingFindingSeverity,
    ModeloIdentifier,
)
from ._repository import (
    SubmissionMigrationSummary,
    SubmissionRepository,
    migrate_legacy_submissions_to_repository,
)

__all__ = [
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
    "SubmissionMigrationSummary",
    "SubmissionPreflightError",
    "SubmissionRepository",
    "SubmissionStatus",
    "SubmittedFiling",
    "make_submission_id",
    "migrate_legacy_submissions_to_repository",
]
