"""Submission lifecycle domain package."""

from __future__ import annotations

from .._identifiers import ModeloIdentifier
from ._engine import SubmissionEngine
from ._errors import SubmissionError, SubmissionPreflightError
from ._models import SubmissionAttempt, SubmissionStatus, ModeloPresentado, make_submission_id
from ._preflight import Preflight
from ._protocols import (
    AuthProviderProbe,
    DeadlineWindowChecker,
    ModeloDraftLoader,
    ModeloDraftStatus,
    ModeloDraftLike,
    ModeloFinding,
)
from ._repository import (
    SubmissionRepository,
)

__all__ = [
    "AuthProviderProbe",
    "DeadlineWindowChecker",
    "ModeloDraftLoader",
    "ModeloDraftStatus",
    "ModeloDraftLike",
    "ModeloFinding",
    "ModeloIdentifier",
    "Preflight",
    "SubmissionAttempt",
    "SubmissionEngine",
    "SubmissionError",
    "SubmissionPreflightError",
    "SubmissionRepository",
    "SubmissionStatus",
    "ModeloPresentado",
    "make_submission_id",
]
