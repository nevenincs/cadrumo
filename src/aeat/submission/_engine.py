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

from ..config import Settings
from ..filing import FilingAmendment, FilingDraft
from ..logging import get_logger
from ._errors import (
    LiveSubmitForbiddenError,
    SubmissionError,
)

# Repository imports (SubmissionRepository, FilingAmendmentRepository)
# are intentionally deferred inside the engine's persist + load + list
# helpers. Both transitively pull ``aeat.storage``, which imports
# Alembic plugin discovery and emits INFO log lines on stderr at import
# time. CLI commands that never touch the engine's persist path must
# not pay that cost; deferring keeps the json-pipe-safety contract
# intact.
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
from ._submitters import BrowserSessionLike, Submitter

_logger = get_logger(__name__)


class SubmissionEngine:
    """Orchestrates preflight, submitter dispatch, and persistence.

    The engine is dry-run-only. Any attempt to invoke a live AEAT
    write raises :class:`LiveSubmitForbiddenError`.
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
        **legacy_live_kwargs: object,
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
            **legacy_live_kwargs: Historical compatibility trap. Any
                unexpected legacy transport keyword now receives
                :class:`LiveSubmitForbiddenError` instead of silently
                re-opening a write path.
        """
        if legacy_live_kwargs:
            raise LiveSubmitForbiddenError(
                "SubmissionEngine no longer accepts historical "
                "live-transport compatibility keywords; live AEAT "
                "submission is permanently forbidden"
            )
        self.browser_session_factory = browser_session_factory
        self.auth_provider = auth_provider
        self.portal_catalogue = portal_catalogue
        self.draft_loader = draft_loader
        self.deadline_checker = deadline_checker
        self.casilla_catalogue = casilla_catalogue
        self.justificante_parser = justificante_parser
        self.submitters = dict(submitters)
        self.settings = settings
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
                execution is requested.
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
        """Submit ``amendment`` through the dry-run-only transport.

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
        if not dry_run:
            raise LiveSubmitForbiddenError()
        reference_today = today or date.today()
        self.preflight(draft_like, today=reference_today)
        if draft.modelo not in self.submitters:
            raise SubmissionError(f"no submitter registered for modelo {draft.modelo!r}")
        submitter = self.submitters[draft.modelo]
        portal = self.portal_catalogue.portal_for(draft.modelo)

        submission_id = make_submission_id(draft.draft_id, attempt_ordinal=1)
        session = self.browser_session_factory()
        justificante_csv: str | None = None
        justificante_pdf_path: Path | None = None

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
        return filing

    def _submission_repository(self):  # type: ignore[no-untyped-def]
        from ._repository import SubmissionRepository

        return SubmissionRepository(store_dir=self.settings.aeat_submissions_dir)

    def _amendment_repository(self):  # type: ignore[no-untyped-def]
        from ..filing._complementaria_repository import FilingAmendmentRepository

        return FilingAmendmentRepository(
            store_dir=self.settings.aeat_submissions_dir / "amendment-results",
        )

    def _persist(self, filing: SubmittedFiling) -> None:
        """Persist ``filing`` through the governed submission repository."""
        try:
            self._submission_repository().save(filing)
        except ValueError as exc:
            raise SubmissionError(
                f"submission id {filing.submission_id!r}: expected a simple filename token: {exc}"
            ) from exc
        _logger.info("engine: persisted submission_id=%s", filing.submission_id)

    def _persist_amendment_result(self, result: AmendmentSubmissionResult) -> None:
        """Persist ``result.amendment`` through the governed amendment repository."""
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
