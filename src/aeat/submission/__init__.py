"""Filing submission engine — the final leg of the AEAT filing loop.

The :class:`SubmissionEngine` composes an authenticated browser
session, a pluggable :class:`Submitter` per modelo, and a strict
:class:`Preflight` validator to drive a ``READY_TO_SUBMIT``
``FilingDraft`` (from #39) through the AEAT presentation portal. The
engine is **dry-run by default**: every call to
:meth:`SubmissionEngine.submit_draft` walks the portal up to (but not
including) the final submit click unless the caller explicitly passes
``dry_run=False``. Live mode is then hard-gated inside the engine by
the live-submit env vars, the pytest refusal check, a blocking
confirmation phrase, and the append-only audit log.

Public API discipline: callers outside this subpackage must import
only from :mod:`aeat.submission` (the package root); the underscored
submodules are implementation detail.

See ``[[2026-04-12-submission-engine-research]]`` and
``[[2026-04-12-submission-engine-adr]]`` for the architectural
context.
"""

from __future__ import annotations

from ._engine import SubmissionEngine
from ._errors import (
    AeatLiveConfirmationDeclinedError,
    AeatLiveSubmitNotEnabledError,
    AeatLiveTransportUnavailableError,
    AeatPytestLiveWriteRefusedError,
    SubmissionError,
    SubmissionFormFillError,
    SubmissionPreflightError,
    SubmissionRejectionError,
)
from ._models import (
    AmendmentSubmissionResult,
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
    CasillaCatalogue,
    CasillaInputKind,
    CasillaRecord,
    DeadlineWindowChecker,
    DraftLoader,
    DraftStatus,
    FilingDraftLike,
    FilingFinding,
    FilingFindingSeverity,
    Justificante,
    JustificanteParser,
    ModeloIdentifier,
    Portal,
    PortalCatalogue,
)
from ._submitters import Submitter
from ._submitters._contract import BrowserSessionLike
from ._submitters.modelo130 import Modelo130Submitter

__all__ = [
    "AeatLiveConfirmationDeclinedError",
    "AeatLiveSubmitNotEnabledError",
    "AeatLiveTransportUnavailableError",
    "AeatPytestLiveWriteRefusedError",
    "AmendmentSubmissionResult",
    "AuthProviderDescription",
    "AuthProviderKind",
    "AuthProviderProbe",
    "BrowserSessionLike",
    "CasillaCatalogue",
    "CasillaInputKind",
    "CasillaRecord",
    "DeadlineWindowChecker",
    "DraftLoader",
    "DraftStatus",
    "FilingDraftLike",
    "FilingFinding",
    "FilingFindingSeverity",
    "Justificante",
    "JustificanteParser",
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
