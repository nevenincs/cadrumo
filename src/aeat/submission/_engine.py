"""Composition root for the filing submission engine.

:class:`SubmissionEngine` wires Preflight, the per-modelo
:class:`Submitter` registry, the in-flight-sibling Protocols, and
Settings into one async entry point —
:meth:`SubmissionEngine.submit_draft`.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast

from ..auth import AeatAccessGate
from ..config import Settings
from ..filing import FilingAmendment, FilingDraft
from ..filing._complementaria_repository import FilingAmendmentRepository
from ..logging import get_logger
from ._audit import build_live_submit_audit_record
from ._confirm import confirm_live_submission
from ._errors import (
    AeatLiveTransportUnavailableError,
    SubmissionError,
)
from ._governed_audit import GovernedLiveSubmitAuditSink
from ._models import (
    AmendmentSubmissionResult,
    SubmissionAttempt,
    SubmissionStatus,
    SubmittedFiling,
    make_submission_id,
)
from ._preflight import Preflight
from ._protocols import (
    AuthProviderProbe,
    CasillaCatalogue,
    DeadlineWindowChecker,
    DraftLoader,
    FilingDraftLike,
    JustificanteParser,
    PortalCatalogue,
)
from ._repository import SubmissionRepository
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
        auth_provider: AuthProviderProbe,
        portal_catalogue: PortalCatalogue,
        draft_loader: DraftLoader,
        deadline_checker: DeadlineWindowChecker,
        casilla_catalogue: CasillaCatalogue,
        justificante_parser: JustificanteParser,
        submitters: Mapping[str, Submitter],
        settings: Settings,
        live_transport_supported: bool = False,
        live_submit_audit_dir: Path | None = None,
    ) -> None:
        """Construct a :class:`SubmissionEngine`.

        Args:
            browser_session_factory: Zero-argument factory returning a
                fresh :class:`BrowserSessionLike`.
            auth_provider: Auth-provider Protocol implementation.
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
            live_transport_supported: Whether this engine is wired
                to a real transport that may perform a live AEAT write.
                **Default is False — opt-in only.** With the default,
                :meth:`submit_draft` with ``dry_run=False`` raises
                :class:`AeatLiveTransportUnavailableError`. See
                ``.vault/adr/2026-04-18-live-submit-cli-excision-adr.md``
                for the rationale (charter #197 + #116).
            live_submit_audit_dir: Optional override for the governed
                live-submit audit sink's audit directory. When ``None``
                the engine binds to ``settings.aeat_audit_dir``. Tests
                that need to inspect the JSONL on disk pass an explicit
                temp directory here.
        """
        self.browser_session_factory = browser_session_factory
        self.auth_provider = auth_provider
        self.portal_catalogue = portal_catalogue
        self.draft_loader = draft_loader
        self.deadline_checker = deadline_checker
        self.casilla_catalogue = casilla_catalogue
        self.justificante_parser = justificante_parser
        self.submitters = dict(submitters)
        self.settings = settings
        self.live_transport_supported = live_transport_supported
        self.live_submit_audit_dir = live_submit_audit_dir
        self._preflight = Preflight(
            deadline_checker=deadline_checker,
            auth_provider=auth_provider,
        )

    def preflight(self, draft: FilingDraftLike, *, today: date) -> None:
        """Run the engine's preflight gates without dispatching a submission."""

        self._preflight.check(draft, today=today)

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
        self.preflight(draft_like, today=reference_today)

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
            gate = AeatAccessGate(self.settings)
            gate.require_live_write()
            # Gate is constructed inline from Settings — never injected,
            # never stored on self, never accepted as a kwarg on the
            # engine. This preserves R5 of the live-write safety
            # charter (#116): no substitutable dependency on the
            # write-gate. The three inline checks above (lines 207-212)
            # remain the authoritative gate; the snapshot is consumed
            # only by the audit log.
            audit_env_state = gate.snapshot_env().as_audit_dict()
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
            audit_sink = self._audit_sink()
            audit_sink.append(
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
                audit_sink.append(
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
            self._audit_sink().append(
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
            )
        return filing

    def _submission_repository(self) -> SubmissionRepository:
        return SubmissionRepository(store_dir=self.settings.aeat_submissions_dir)

    def _audit_sink(self) -> GovernedLiveSubmitAuditSink:
        """Return the governed live-submit audit sink for this engine.

        Routes through the override audit dir when one is supplied (test
        fixtures that need to inspect the JSONL); otherwise binds to the
        operator-configured ``aeat_audit_dir``.
        """
        return GovernedLiveSubmitAuditSink(
            audit_dir=self.live_submit_audit_dir or self.settings.aeat_audit_dir,
        )

    def _amendment_repository(self) -> FilingAmendmentRepository:
        return FilingAmendmentRepository(
            store_dir=self.settings.aeat_submissions_dir / "amendment-results",
        )

    def _persist(self, filing: SubmittedFiling) -> None:
        """Persist ``filing`` through the governed submission repository."""
        try:
            self._submission_repository().save(filing)
        except ValueError as exc:
            # Repository validators reject path-traversal-shaped ids; map
            # to the engine's SubmissionError contract while preserving
            # the historical "simple filename token" phrase consumers
            # match against.
            raise SubmissionError(
                f"submission id {filing.submission_id!r}: expected a simple filename token: {exc}"
            ) from exc
        _logger.info("engine: persisted submission_id=%s", filing.submission_id)

    def _persist_amendment_result(self, result: AmendmentSubmissionResult) -> None:
        """Persist ``result.amendment`` through the governed amendment repository.

        The transport-level wrapper (`AmendmentSubmissionResult.dry_run`,
        `submitted_at`) is dropped — the inner :class:`FilingAmendment`
        is the load-bearing audit record. No production reader consumes
        the wrapper today; if a future caller needs the wrapper fields
        they can be added back as a dedicated repository.
        """
        try:
            self._amendment_repository().save(result.amendment)
        except ValueError as exc:
            raise SubmissionError(
                f"amendment id {result.amendment_id!r}: expected a simple filename token: {exc}"
            ) from exc
        _logger.info("engine: persisted amendment_id=%s", result.amendment_id)

    def load_submission(self, submission_id: str) -> SubmittedFiling:
        """Load a persisted :class:`SubmittedFiling` by id.

        Args:
            submission_id: The submission identifier.

        Returns:
            The :class:`SubmittedFiling` previously written through the
            governed repository.

        Raises:
            SubmissionError: If no record exists for ``submission_id``
                or if ``submission_id`` is not a simple filename token.
        """
        try:
            filing = self._submission_repository().load(submission_id)
        except ValueError as exc:
            raise SubmissionError(f"submission id {submission_id!r}: expected a simple filename token: {exc}") from exc
        if filing is None:
            raise SubmissionError(f"no persisted submission with id {submission_id!r}")
        return filing

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
        repository = self._submission_repository()
        results: list[SubmittedFiling] = []
        for filing in repository.iter_submissions():
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
