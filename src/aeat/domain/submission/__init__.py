"""Public facade for local-only submission audit records.

This package exposes preflight gates, historical/imported audit records,
repository storage, and narrow protocol types for submission-adjacent flows.
:class:`SubmissionEngine` is read-only: it runs :class:`Preflight` and reads
persisted :class:`ModeloPresentado` records. It does not present to AEAT, create
submission records, or transition a draft or revision into ``presentado``.

:class:`Preflight` checks approved draft status, absence of error findings, the
deadline window unless skipped, and auth-provider readiness. The engine depends
on deadline and auth-provider probes; :class:`ModeloDraftLoader` remains an
exported adapter contract, not a dependency consumed by :class:`SubmissionEngine`.

:class:`ModeloPresentado` is a strict local-only historical/imported audit
record stored by :class:`SubmissionRepository` as encrypted AUDIT data under
``aeat.domain.submission.records``. It is distinct from
:class:`aeat.domain.modelos.ModeloRecord`: :func:`aeat.application.modelo.file_modelo_revision`
creates a local work-unit filing record with ``aeat_accepted=False`` and no
external evidence, while
:func:`aeat.application.filing.import_filing_from_justificante` imports
historical filing evidence into the audit trail.

Live AEAT writes are blocked by
:meth:`aeat.core.access_gate.AeatAccessGate.require_live_write`, which raises
:exc:`aeat.core.access_gate.LiveSubmitForbiddenError`; preflight denials raise
:exc:`SubmissionPreflightError`.

Major declarations:

* :class:`SubmissionEngine` — runs preflight and reads historical audit records.
* :class:`Preflight` and :exc:`SubmissionPreflightError` — the
  pre-submission checks and their refusal.
* :class:`ModeloPresentado`, :class:`SubmissionAttempt`, and
  :class:`SubmissionStatus` — the persisted lifecycle records, keyed by
  :func:`make_submission_id`.
* :class:`SubmissionRepository` — the persistence boundary.
* The :class:`ModeloDraftLoader`, :class:`ModeloDraftLike`,
  :class:`DeadlineWindowChecker`, and :class:`AuthProviderProbe` protocols —
  exported narrow contracts that keep the domain free of live adapters.

See Also:
    - :func:`aeat.application.modelo.file_modelo_revision` for the local
      work-unit filing action that creates :class:`aeat.domain.modelos.ModeloRecord`
      entries without AEAT acceptance.
    - :mod:`aeat.application.live` for read-only AEAT evidence capture and
      justificante verification; it is not a live-submit path.
    - :func:`aeat.application.filing.import_filing_from_justificante` for
      importing historical filing evidence into the submission audit trail.
    - :mod:`aeat.domain.filing` for draft construction and review records used
      before preflight or evidence import.
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
