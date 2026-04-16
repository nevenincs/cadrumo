"""Composition root for the filing submission engine.

:class:`SubmissionEngine` wires Preflight, the per-modelo
:class:`Submitter` registry, the in-flight-sibling Protocols, and
Settings into one async entry point —
:meth:`SubmissionEngine.submit_draft`.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast

from aeat.config import Settings
from aeat.filing import FilingAmendment, FilingDraft
from aeat.logging import get_logger
from aeat.submission._audit import (
    LiveSubmitAuditRecord,
    SubmissionAuditEvent,
    append_audit_record,
    build_audit_record,
    default_audit_log_path,
    read_audit_records,
)
from aeat.submission._confirm import confirm_live_submission
from aeat.submission._errors import (
    AeatLiveSubmitNotEnabledError,
    AeatPytestLiveWriteRefusedError,
    SubmissionError,
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
    CertificateBackend,
    DeadlineWindowChecker,
    DraftLoader,
    FilingDraftLike,
    JustificanteParser,
    PortalCatalogue,
)
from aeat.submission._submitters import BrowserSessionLike, Submitter

_logger = get_logger(__name__)


class SubmissionEngine:
    """Orchestrates preflight, submitter dispatch, and persistence.

    The engine is dry-run-by-default and double-gates every live
    submission. See [[2026-04-12-submission-engine-adr]] for the
    rationale.
    """

    def __init__(
        self,
        *,
        browser_session_factory: Callable[[], BrowserSessionLike],
        cert_backend: CertificateBackend,
        portal_catalogue: PortalCatalogue,
        draft_loader: DraftLoader,
        deadline_checker: DeadlineWindowChecker,
        casilla_catalogue: CasillaCatalogue,
        justificante_parser: JustificanteParser,
        submitters: Mapping[str, Submitter],
        settings: Settings,
        audit_log_path: Path | None = None,
    ) -> None:
        """Construct a :class:`SubmissionEngine`.

        Args:
            browser_session_factory: Zero-argument factory returning a
                fresh :class:`BrowserSessionLike`.
            cert_backend: Certificate Protocol implementation.
            portal_catalogue: Portal catalogue Protocol implementation.
            draft_loader: Draft loader Protocol (used by the CLI to
                read drafts off disk; the engine itself accepts
                already-loaded drafts).
            deadline_checker: Deadline window Protocol.
            casilla_catalogue: Casilla catalogue Protocol.
            justificante_parser: Justificante parser Protocol.
            submitters: Mapping ``modelo -> Submitter`` dispatched by
                :meth:`submit_draft`.
            settings: Application settings.
        """
        self.browser_session_factory = browser_session_factory
        self.cert_backend = cert_backend
        self.portal_catalogue = portal_catalogue
        self.draft_loader = draft_loader
        self.deadline_checker = deadline_checker
        self.casilla_catalogue = casilla_catalogue
        self.justificante_parser = justificante_parser
        self.submitters = dict(submitters)
        self.settings = settings
        self.audit_log_path = audit_log_path or default_audit_log_path(submissions_dir=settings.aeat_submissions_dir)
        self._preflight = Preflight(
            deadline_checker=deadline_checker,
            cert_backend=cert_backend,
        )

    async def submit_draft(
        self,
        draft: FilingDraftLike,
        *,
        dry_run: bool,
        today: date | None = None,
    ) -> SubmittedFiling:
        """Run preflight + dispatch to the per-modelo submitter.

        Args:
            draft: The :class:`FilingDraftLike` to submit.
            dry_run: When ``True`` the submitter's ``dry_run`` method
                is called and the resulting filing status is
                :attr:`SubmissionStatus.PENDING`. When ``False`` the
                hardened live-submit gate path is entered.
            today: Reference date for the preflight deadline gate.
                Defaults to :meth:`date.today`.

        Returns:
            The :class:`SubmittedFiling` audit record. Always
            persisted as JSON under ``settings.aeat_submissions_dir``.

        Raises:
            SubmissionError: If no submitter is registered for
                ``draft.modelo``.
        """
        return await self._submit_with_transport(
            draft=draft,
            dry_run=dry_run,
            today=today,
        )

    async def submit_amendment(
        self,
        amendment: FilingAmendment,
        *,
        dry_run: bool,
        today: date | None = None,
    ) -> AmendmentSubmissionResult:
        """Submit ``amendment`` through the existing per-modelo transport.

        Args:
            amendment: The amendment produced by
                :func:`aeat.filing.build_complementaria`.
            dry_run: When ``True``, stop before the final
                irreversible submission click.
            today: Optional preflight reference date.

        Returns:
            A typed :class:`AmendmentSubmissionResult` persisted under
            ``settings.aeat_submissions_dir``.
        """
        filing = await self._submit_with_transport(
            draft=amendment.amended_draft,
            dry_run=dry_run,
            today=today,
            amendment_kind=amendment.amendment_kind.value,
            original_csv=amendment.original_csv,
        )
        result = AmendmentSubmissionResult(
            amendment_id=amendment.amendment_id,
            amendment=amendment,
            filing=filing,
            dry_run=dry_run,
            submitted_at=filing.submitted_at,
        )
        self._persist_amendment_result(result)
        return result

    async def _submit_with_transport(
        self,
        *,
        draft: FilingDraftLike | FilingDraft,
        dry_run: bool,
        today: date | None,
        amendment_kind: str | None = None,
        original_csv: str | None = None,
    ) -> SubmittedFiling:
        """Execute the shared preflight + transport flow."""
        draft_like = cast(FilingDraftLike, draft)
        reference_today = today or date.today()
        self._preflight.check(draft_like, today=reference_today)

        if draft.modelo not in self.submitters:
            raise SubmissionError(f"no submitter registered for modelo {draft.modelo!r}")
        submitter = self.submitters[draft.modelo]
        portal = self.portal_catalogue.portal_for(draft.modelo)
        submission_id = make_submission_id(draft.draft_id, attempt_ordinal=1)

        justificante_csv: str | None = None
        justificante_pdf_path: Path | None = None

        if dry_run:
            session = self.browser_session_factory()
            _logger.info("engine: dry-run submitting modelo=%s", draft.modelo)
            try:
                attempt = await submitter.dry_run(
                    draft=draft_like,
                    session=session,
                    casilla_catalogue=self.casilla_catalogue,
                    portal=portal,
                    amendment_kind=amendment_kind,
                    original_csv=original_csv,
                )
            except Exception as exc:
                self._append_audit_record(
                    build_audit_record(
                        event=SubmissionAuditEvent.DRY_RUN,
                        submission_id=submission_id,
                        draft=draft_like,
                        dry_run=True,
                        status=SubmissionStatus.FAILED.value,
                        reason=str(exc),
                        error_type=exc.__class__.__name__,
                    )
                )
                raise
            overall_status = SubmissionStatus.PENDING
            attempts: tuple[SubmissionAttempt, ...] = (attempt,)
        else:
            self._guard_live_submission(submission_id=submission_id, draft=draft_like)
            self._append_audit_record(
                build_audit_record(
                    event=SubmissionAuditEvent.LIVE_REQUESTED,
                    submission_id=submission_id,
                    draft=draft_like,
                    dry_run=False,
                    status=SubmissionStatus.IN_PROGRESS.value,
                )
            )
            session = self.browser_session_factory()
            _logger.info("engine: LIVE submitting modelo=%s", draft.modelo)
            try:
                attempt, justificante = await submitter.submit(
                    draft=draft_like,
                    session=session,
                    casilla_catalogue=self.casilla_catalogue,
                    portal=portal,
                    amendment_kind=amendment_kind,
                    original_csv=original_csv,
                )
            except Exception as exc:
                self._append_audit_record(
                    build_audit_record(
                        event=SubmissionAuditEvent.LIVE_RESULT,
                        submission_id=submission_id,
                        draft=draft_like,
                        dry_run=False,
                        status=SubmissionStatus.FAILED.value,
                        reason=str(exc),
                        error_type=exc.__class__.__name__,
                    )
                )
                raise
            overall_status = SubmissionStatus.SUBMITTED
            attempts = (attempt,)
            if justificante is not None:
                justificante_csv = justificante.csv
                justificante_pdf_path = justificante.pdf_path

        filing = SubmittedFiling(
            submission_id=submission_id,
            draft_id=draft.draft_id,
            modelo=draft.modelo,
            period=draft.period,
            profile_tax_id=draft.profile_tax_id,
            status=overall_status,
            justificante_csv=justificante_csv,
            justificante_pdf_path=justificante_pdf_path,
            submitted_at=attempts[0].started_at,
            acknowledged_at=None,
            attempts=attempts,
        )
        self._append_audit_record(
            build_audit_record(
                event=SubmissionAuditEvent.DRY_RUN if dry_run else SubmissionAuditEvent.LIVE_RESULT,
                submission_id=submission_id,
                draft=draft_like,
                dry_run=dry_run,
                status=filing.status.value,
                justificante_csv=filing.justificante_csv,
            )
        )
        self._persist(filing)
        return filing

    def supports_live_submission(self) -> bool:
        """Return ``True`` when the configured session factory can really submit live."""
        return bool(getattr(self.browser_session_factory, "supports_live_submission", True))

    def _persist(self, filing: SubmittedFiling) -> None:
        """Write ``filing`` as pretty JSON under ``aeat_submissions_dir``."""
        target_dir = self.settings.aeat_submissions_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{filing.submission_id}.json"
        target.write_text(filing.model_dump_json(indent=2), encoding="utf-8")
        _logger.info("engine: persisted %s", target)

    def _persist_amendment_result(self, result: AmendmentSubmissionResult) -> None:
        """Write ``result`` as pretty JSON under ``aeat_submissions_dir/amendment-results``."""
        target_dir = self.settings.aeat_submissions_dir / "amendment-results"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{result.amendment_id}.json"
        target.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        _logger.info("engine: persisted amendment result %s", target)

    def load_submission(self, submission_id: str) -> SubmittedFiling:
        """Load a persisted :class:`SubmittedFiling` by id.

        Args:
            submission_id: The submission identifier.

        Returns:
            The :class:`SubmittedFiling` previously written to
            ``settings.aeat_submissions_dir``.

        Raises:
            SubmissionError: If no record exists for ``submission_id``.
        """
        target = self.settings.aeat_submissions_dir / f"{submission_id}.json"
        if not target.exists():
            raise SubmissionError(f"no persisted submission with id {submission_id!r}")
        return SubmittedFiling.model_validate_json(target.read_text(encoding="utf-8"))

    def list_audit_records(self, *, limit: int | None = None) -> tuple[LiveSubmitAuditRecord, ...]:
        """Return audit records from the append-only submission audit log."""
        return read_audit_records(self.audit_log_path, limit=limit)

    def list_submissions(
        self,
        *,
        modelo: str | None = None,
        status: SubmissionStatus | None = None,
    ) -> tuple[SubmittedFiling, ...]:
        """Return every persisted :class:`SubmittedFiling`, optionally filtered.

        Args:
            modelo: If set, only include filings for this modelo.
            status: If set, only include filings with this status.

        Returns:
            A tuple of filings sorted by ``submitted_at`` descending.
        """
        target_dir = self.settings.aeat_submissions_dir
        if not target_dir.exists():
            return ()
        results: list[SubmittedFiling] = []
        for path in sorted(target_dir.glob("*.json")):
            try:
                filing = SubmittedFiling.model_validate_json(path.read_text(encoding="utf-8"))
            except Exception as exc:  # pragma: no cover - defensive
                _logger.warning("engine: skipping unreadable record %s: %s", path, exc)
                continue
            if modelo is not None and filing.modelo != modelo:
                continue
            if status is not None and filing.status != status:
                continue
            results.append(filing)
        results.sort(key=lambda f: f.submitted_at, reverse=True)
        return tuple(results)

    def _guard_live_submission(self, *, submission_id: str, draft: FilingDraftLike) -> None:
        """Refuse live submission unless every hardened gate passes."""
        if os.getenv("PYTEST_CURRENT_TEST"):
            error = AeatPytestLiveWriteRefusedError("live submission refused because PYTEST_CURRENT_TEST is present")
            self._append_live_refusal(submission_id=submission_id, draft=draft, error=error)
            raise error
        if not self.settings.aeat_live_submit_enabled:
            error = AeatLiveSubmitNotEnabledError("live submission requires AEAT_LIVE_SUBMIT_ENABLED=true")
            self._append_live_refusal(submission_id=submission_id, draft=draft, error=error)
            raise error
        try:
            confirm_live_submission(
                draft=draft,
                draft_checksum_sha256=self._draft_checksum(draft),
            )
        except Exception as exc:
            self._append_live_refusal(submission_id=submission_id, draft=draft, error=exc)
            raise

    def _append_live_refusal(
        self,
        *,
        submission_id: str,
        draft: FilingDraftLike,
        error: Exception,
    ) -> None:
        """Record one refused live-submit attempt."""
        self._append_audit_record(
            build_audit_record(
                event=SubmissionAuditEvent.LIVE_REFUSED,
                submission_id=submission_id,
                draft=draft,
                dry_run=False,
                status="REFUSED",
                reason=str(error),
                error_type=error.__class__.__name__,
            )
        )

    def _append_audit_record(self, record: LiveSubmitAuditRecord) -> None:
        """Append one audit record to the configured append-only log."""
        append_audit_record(self.audit_log_path, record)

    def _draft_checksum(self, draft: FilingDraftLike) -> str:
        """Return the stable checksum used in confirmation and audit records."""
        return build_audit_record(
            event=SubmissionAuditEvent.DRY_RUN,
            submission_id="checksum-only",
            draft=draft,
            dry_run=True,
            status=SubmissionStatus.PENDING.value,
        ).draft_checksum_sha256


def _created_at_now() -> datetime:
    """Return ``datetime.now(UTC)``; factored out for test determinism hooks."""
    return datetime.now(UTC)
