"""Filing submission engine — the final leg of the AEAT filing loop.

The :class:`SubmissionEngine` composes an authenticated browser
session, a pluggable :class:`Submitter` per modelo, and a strict
:class:`Preflight` validator to drive a ``READY_TO_SUBMIT``
``FilingDraft`` (from #39) through the AEAT presentation portal. The
engine is **dry-run by default**: every call to
:meth:`SubmissionEngine.submit_draft` walks the portal up to (but not
including) the final submit click unless the caller explicitly passes
``dry_run=False`` **and** ``override_confirmation=True``. AEAT
submissions are irreversible legal acts; the double gate is a
non-negotiable safety net.

Public API discipline: callers outside this subpackage must import
only from :mod:`aeat.submission` (the package root); the underscored
submodules are implementation detail.

See ``[[2026-04-12-submission-engine-research]]`` and
``[[2026-04-12-submission-engine-adr]]`` for the architectural
context.
"""

from __future__ import annotations

from aeat.submission._engine import SubmissionEngine
from aeat.submission._errors import (
    SubmissionError,
    SubmissionFormFillError,
    SubmissionPreflightError,
    SubmissionRejectionError,
)
from aeat.submission._models import (
    AmendmentSubmissionResult,
    SubmissionAttempt,
    SubmissionStatus,
    SubmittedFiling,
    make_submission_id,
)
from aeat.submission._preflight import Preflight
from aeat.submission._protocols import (
    CasillaCatalogue,
    CasillaInputKind,
    CasillaRecord,
    CertificateBackend,
    DeadlineWindowChecker,
    DraftLoader,
    DraftStatus,
    FilingDraftLike,
    FilingFinding,
    FilingFindingSeverity,
    Justificante,
    JustificanteParser,
    LoadedCertificate,
    ModeloIdentifier,
    Portal,
    PortalCatalogue,
)
from aeat.submission._submitters import Submitter
from aeat.submission._submitters._contract import BrowserSessionLike
from aeat.submission._submitters.modelo130 import Modelo130Submitter

__all__ = [
    "AmendmentSubmissionResult",
    "BrowserSessionLike",
    "CasillaCatalogue",
    "CasillaInputKind",
    "CasillaRecord",
    "CertificateBackend",
    "DeadlineWindowChecker",
    "DraftLoader",
    "DraftStatus",
    "FilingDraftLike",
    "FilingFinding",
    "FilingFindingSeverity",
    "Justificante",
    "JustificanteParser",
    "LoadedCertificate",
    "Modelo130Submitter",
    "ModeloIdentifier",
    "Portal",
    "PortalCatalogue",
    "Preflight",
    "SubmissionAttempt",
    "SubmissionEngine",
    "SubmissionError",
    "SubmissionFormFillError",
    "SubmissionPreflightError",
    "SubmissionRejectionError",
    "SubmissionStatus",
    "SubmittedFiling",
    "Submitter",
    "make_submission_id",
]
