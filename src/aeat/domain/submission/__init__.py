"""Submission lifecycle domain: the internal "filed" state machine.

Models the local-only submission lifecycle that marks a verified modelo
revision as internally filed (:class:`ModeloPresentado`) and records the
attempt — never a remote AEAT write. The engine runs a preflight before
allowing the transition.

This package is the historical lifecycle model for local ``presentado`` records.
It depends on injected draft-loading, deadline, and auth-probe protocols so the
state transition can be tested without AEAT adapters. Application services own
operator verbs and workflow integration; read-only live capture surfaces may
observe AEAT evidence later, but they do not make this domain engine perform a
remote submission.

Major declarations:

* :class:`SubmissionEngine` — drives a draft through preflight to the
  ``presentado`` state.
* :class:`Preflight` and :class:`SubmissionPreflightError` — the
  pre-submission checks and their refusal.
* :class:`ModeloPresentado`, :class:`SubmissionAttempt`, and
  :class:`SubmissionStatus` — the persisted lifecycle records, keyed by
  :func:`make_submission_id`.
* :class:`SubmissionRepository` — the persistence boundary.
* The :class:`ModeloDraftLoader`, :class:`ModeloDraftLike`,
  :class:`DeadlineWindowChecker`, and :class:`AuthProviderProbe` protocols —
  injected dependencies that keep the domain free of adapters.

See Also:
    - :mod:`aeat.application.modelo` for operator-facing work-unit filing
      actions that coordinate verified calculation revisions with local filing
      records.
    - :mod:`aeat.application.live` for read-only AEAT evidence capture and
      justificante verification; it is not a live-submit path.
    - :mod:`aeat.domain.filing` for draft construction and review records used
      before a submission lifecycle transition.
"""

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
