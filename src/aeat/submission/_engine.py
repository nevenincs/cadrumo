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

from .._paths import resolve_record_json_path
from ..config import Settings
from ..filing import FilingAmendment, FilingDraft
from ..logging import get_logger
from ._audit import append_live_submit_audit, build_live_submit_audit_record
from ._confirm import confirm_live_submission
from ._errors import (
    AeatLiveSubmitNotEnabledError,
    AeatLiveTransportUnavailableError,
    AeatPytestLiveWriteRefusedError,
    SubmissionError,
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
    CasillaCatalogue,
    CertificateBackend,
    DeadlineWindowChecker,
    DraftLoader,
    FilingDraftLike,
    JustificanteParser,
    PortalCatalogue,
)
from ._submitters import BrowserSessionLike, Submitter

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
        live_transport_supported: bool = True,
        live_submit_audit_log_path: Path | None = None,
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
            live_transport_supported: Whether this engine is wired to a
                real transport that may perform a live AEAT write.
            live_submit_audit_log_path: Optional override for the
                append-only live submit audit log path.
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
        self.live_transport_supported = live_transport_supported
        self.live_submit_audit_log_path = live_submit_audit_log_path
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
            dry_run: When ``True`` the submitter's
                ``dry_run`` method is called and the resulting
                filing status is :attr:`SubmissionStatus.PENDING`.
            today: Reference date for the preflight deadline gate.
                Defaults to :meth:`date.today`.

        Returns:
            The :class:`SubmittedFiling` audit record. Always
            persisted as JSON under ``settings.aeat_submissions_dir``.

        Raises:
            SubmissionPreflightError: If preflight fails, or if live
                mode is requested without the full double-gate.
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
        confirmation = None
        audit_env_state: dict[str, str] | None = None

        if not dry_run:
            if not self.live_transport_supported:
                raise AeatLiveTransportUnavailableError(
                    "live submission requires a real browser/certificate transport; this engine is stubbed"
                )
            if not self.settings.aeat_live_submit_enabled:
                raise AeatLiveSubmitNotEnabledError("live submission requires AEAT_LIVE_SUBMIT_ENABLED=true")
            if "PYTEST_CURRENT_TEST" in os.environ:
                raise AeatPytestLiveWriteRefusedError(
                    "pytest may never execute a live AEAT write; refusing dry_run=False submission"
                )
            audit_env_state = {
                "AEAT_LIVE_TESTS_ENABLED": os.environ.get("AEAT_LIVE_TESTS_ENABLED", ""),
                "AEAT_LIVE_SUBMIT_ENABLED": os.environ.get("AEAT_LIVE_SUBMIT_ENABLED", ""),
                "PYTEST_CURRENT_TEST": os.environ.get("PYTEST_CURRENT_TEST", ""),
            }
            confirmation = confirm_live_submission(draft_like, portal=portal)

        submission_id = make_submission_id(draft.draft_id, attempt_ordinal=1)
        session = self.browser_session_factory()
        justificante_csv: str | None = None
        justificante_pdf_path: Path | None = None

        if dry_run:
            _logger.info("engine: dry-run submitting modelo=%s", draft.modelo)
            attempt = await submitter.dry_run(
                draft=draft_like,
                session=session,
                casilla_catalogue=self.casilla_catalogue,
                portal=portal,
                amendment_kind=amendment_kind,
                original_csv=original_csv,
            )
            overall_status = SubmissionStatus.PENDING
            attempts: tuple[SubmissionAttempt, ...] = (attempt,)
        else:
            _logger.info("engine: LIVE submitting modelo=%s", draft.modelo)
            assert confirmation is not None
            assert audit_env_state is not None
            append_live_submit_audit(
                build_live_submit_audit_record(
                    modelo=draft.modelo,
                    period=draft.period,
                    taxpayer_nif=draft.profile_tax_id,
                    draft_checksum=confirmation.draft_checksum,
                    submission_url=portal.presentation_url,
                    response_status="DISPATCH_REQUESTED",
                    justificante_csv=None,
                    confirmation_phrase=confirmation.typed_phrase,
                    env_state=audit_env_state,
                ),
                target=self.live_submit_audit_log_path,
            )
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
                append_live_submit_audit(
                    build_live_submit_audit_record(
                        modelo=draft.modelo,
                        period=draft.period,
                        taxpayer_nif=draft.profile_tax_id,
                        draft_checksum=confirmation.draft_checksum,
                        submission_url=portal.presentation_url,
                        response_status=f"ERROR:{type(exc).__name__}",
                        justificante_csv=None,
                        confirmation_phrase=confirmation.typed_phrase,
                        env_state=audit_env_state,
                    ),
                    target=self.live_submit_audit_log_path,
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
        self._persist(filing)
        if not dry_run and confirmation is not None:
            append_live_submit_audit(
                build_live_submit_audit_record(
                    modelo=draft.modelo,
                    period=draft.period,
                    taxpayer_nif=draft.profile_tax_id,
                    draft_checksum=confirmation.draft_checksum,
                    submission_url=portal.presentation_url,
                    response_status=attempts[0].status.value,
                    justificante_csv=justificante_csv,
                    confirmation_phrase=confirmation.typed_phrase,
                    env_state=audit_env_state,
                ),
                target=self.live_submit_audit_log_path,
            )
        return filing

    def _persist(self, filing: SubmittedFiling) -> None:
        """Write ``filing`` as pretty JSON under ``aeat_submissions_dir``."""
        target_dir = self.settings.aeat_submissions_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        try:
            target = resolve_record_json_path(target_dir, filing.submission_id, context="submission id")
        except ValueError as exc:
            raise SubmissionError(str(exc)) from exc
        target.write_text(filing.model_dump_json(indent=2), encoding="utf-8")
        _logger.info("engine: persisted %s", target)

    def _persist_amendment_result(self, result: AmendmentSubmissionResult) -> None:
        """Write ``result`` as pretty JSON under ``aeat_submissions_dir/amendment-results``."""
        target_dir = self.settings.aeat_submissions_dir / "amendment-results"
        target_dir.mkdir(parents=True, exist_ok=True)
        try:
            target = resolve_record_json_path(target_dir, result.amendment_id, context="amendment id")
        except ValueError as exc:
            raise SubmissionError(str(exc)) from exc
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
        try:
            target = resolve_record_json_path(
                self.settings.aeat_submissions_dir,
                submission_id,
                context="submission id",
            )
        except ValueError as exc:
            raise SubmissionError(str(exc)) from exc
        if not target.exists():
            raise SubmissionError(f"no persisted submission with id {submission_id!r}")
        return SubmittedFiling.model_validate_json(target.read_text(encoding="utf-8"))

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


def _created_at_now() -> datetime:
    """Return ``datetime.now(UTC)``; factored out for test determinism hooks."""
    return datetime.now(UTC)
