"""Preflight gating for the filing submission engine.

``Preflight`` runs four ordered gates against a
:class:`aeat.submission._protocols.FilingDraftLike` before any
browser work begins. Every failure raises
:class:`SubmissionPreflightError`; the happy path is silent.
"""

from __future__ import annotations

from datetime import date

from ..logging import get_logger
from ._errors import SubmissionPreflightError
from ._protocols import (
    CertificateBackend,
    DeadlineWindowChecker,
    DraftStatus,
    FilingDraftLike,
)

_logger = get_logger(__name__)


class Preflight:
    """Four-gate validator for a :class:`FilingDraftLike`.

    Gates run in order:

    1. Draft status is :attr:`DraftStatus.READY_TO_SUBMIT`.
    2. No ``ERROR``-severity entries in ``draft.findings``.
    3. Deadline window is open via
       :meth:`DeadlineWindowChecker.is_window_open`.
    4. Certificate loads cleanly via :meth:`CertificateBackend.load`.

    The validator is pure: no I/O beyond the injected Protocol calls,
    no state beyond its dependencies.

    Attributes:
        deadline_checker: Protocol implementation used for gate 3.
        cert_backend: Protocol implementation used for gate 4.
    """

    def __init__(
        self,
        *,
        deadline_checker: DeadlineWindowChecker,
        cert_backend: CertificateBackend,
    ) -> None:
        """Construct a preflight validator.

        Args:
            deadline_checker: Protocol used for the deadline-window gate.
            cert_backend: Protocol used for the certificate gate.
        """
        self.deadline_checker = deadline_checker
        self.cert_backend = cert_backend

    def check(self, draft: FilingDraftLike, *, today: date) -> None:
        """Run the four preflight gates against ``draft``.

        Args:
            draft: The :class:`FilingDraftLike` to validate.
            today: Reference date for the deadline-window gate.

        Raises:
            SubmissionPreflightError: If any gate fails. The exception
                message identifies the failing gate.
        """
        _logger.info(
            "preflight start: draft_id=%s modelo=%s period=%s",
            draft.draft_id,
            draft.modelo,
            draft.period,
        )

        status_value = _enum_value(draft.status)
        if status_value == DraftStatus.APPROVAL_STALE.value:
            _logger.info("preflight gate-1 FAIL: draft status=%s", draft.status)
            raise SubmissionPreflightError("draft approval is stale; review and re-approve before submission")
        if status_value not in {
            DraftStatus.READY_TO_SUBMIT.value,
            DraftStatus.APPROVED.value,
        }:
            _logger.info("preflight gate-1 FAIL: draft status=%s", draft.status)
            raise SubmissionPreflightError(f"draft not ready to submit (status={status_value})")
        _logger.info("preflight gate-1 OK: draft status=%s", status_value)

        error_findings = tuple(f for f in draft.findings if _enum_value(getattr(f, "severity", None)) == "ERROR")
        if error_findings:
            _logger.info(
                "preflight gate-2 FAIL: %d ERROR-severity findings",
                len(error_findings),
            )
            raise SubmissionPreflightError(
                f"draft has {len(error_findings)} ERROR-severity finding(s); resolve them before submission"
            )
        _logger.info("preflight gate-2 OK: no ERROR findings")

        if not self.deadline_checker.is_window_open(draft.modelo, draft.period, today):
            _logger.info(
                "preflight gate-3 FAIL: deadline window closed for %s %s on %s",
                draft.modelo,
                draft.period,
                today,
            )
            raise SubmissionPreflightError(
                f"deadline window for modelo {draft.modelo} period {draft.period} is not open on {today.isoformat()}"
            )
        _logger.info("preflight gate-3 OK: deadline window is open")

        try:
            loaded = self.cert_backend.load()
        except Exception as exc:
            _logger.info("preflight gate-4 FAIL: certificate load raised %r", exc)
            raise SubmissionPreflightError(f"certificate backend failed to load: {exc}") from exc
        _logger.info(
            "preflight gate-4 OK: certificate loaded (subject=%s not_after=%s)",
            loaded.subject,
            loaded.not_after,
        )


def _enum_value(value: object) -> str:
    """Return ``Enum.value`` when present, otherwise ``str(value)``."""
    if value is None:
        return ""
    raw = getattr(value, "value", value)
    return str(raw)
