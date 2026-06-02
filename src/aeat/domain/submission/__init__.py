"""Submission lifecycle domain package."""

from __future__ import annotations

from .._identifiers import ModeloIdentifier
from ._engine import SubmissionEngine
from ._errors import SubmissionError, SubmissionPreflightError
from ._models import ModeloPresentado, SubmissionAttempt, SubmissionStatus, make_submission_id
from ._preflight import Preflight
from ._protocols import (
    AuthProviderProbe,
    DeadlineWindowChecker,
    ModeloDraftLike,
    ModeloDraftLoader,
    ModeloDraftStatus,
    ModeloFinding,
)
from ._repository import (
    SubmissionRepository,
)

__all__ = [
    "AuthProviderProbe",
    "DeadlineWindowChecker",
    "ModeloDraftLike",
    "ModeloDraftLoader",
    "ModeloDraftStatus",
    "ModeloFinding",
    "ModeloIdentifier",
    "ModeloPresentado",
    "Preflight",
    "SubmissionAttempt",
    "SubmissionEngine",
    "SubmissionError",
    "SubmissionPreflightError",
    "SubmissionRepository",
    "SubmissionStatus",
    "make_submission_id",
]
