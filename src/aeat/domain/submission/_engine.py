"""Read-only submission record loader and preflight engine.

Exposes :class:`SubmissionEngine`, the only sanctioned surface for
running preflight gates and reading historical
:class:`aeat.domain.submission.SubmittedFiling` records persisted under
:attr:`aeat.core.config.Settings.aeat_submissions_dir`.

AEAT remote writes and write-shaped portal walks are permanently
forbidden; the engine intentionally exposes no transport method.
"""

from __future__ import annotations

from datetime import date

from ...core.config import Settings
from ...core.logging import get_logger
from ...core.paths import resolve_record_json_path
from ._errors import SubmissionError
from ._models import SubmissionStatus, SubmittedFiling
from ._preflight import Preflight
from ._protocols import AuthProviderProbe, DeadlineWindowChecker, FilingDraftLike

_logger = get_logger(__name__)


class SubmissionEngine:
    """Runs preflight and reads historical submission records.

    AEAT remote writes and write-shaped portal walks are permanently
    forbidden. This class intentionally exposes no transport method.

    Attributes:
        auth_provider: Narrow auth-provider probe used by preflight.
        deadline_checker: Narrow window checker used by preflight.
        settings: Resolved :class:`aeat.core.config.Settings` whose
            ``aeat_submissions_dir`` backs :meth:`load_submission` and
            :meth:`list_submissions`.
    """

    def __init__(
        self,
        *,
        auth_provider: AuthProviderProbe,
        deadline_checker: DeadlineWindowChecker,
        settings: Settings,
    ) -> None:
        """Construct a read-only :class:`SubmissionEngine`.

        Args:
            auth_provider: Narrow probe over the active auth provider.
            deadline_checker: Narrow window checker over
                :mod:`aeat.domain.deadlines`.
            settings: Resolved :class:`aeat.core.config.Settings`.
        """
        self.auth_provider = auth_provider
        self.deadline_checker = deadline_checker
        self.settings = settings
        self._preflight = Preflight(
            deadline_checker=deadline_checker,
            auth_provider=auth_provider,
        )

    def preflight(self, draft: FilingDraftLike, *, today: date) -> None:
        """Run preflight gates without browser work or AEAT writes.

        Args:
            draft: Draft conforming to :class:`FilingDraftLike`.
            today: Calendar date used to evaluate the AEAT filing window.
        """
        self._preflight.check(draft, today=today)

    def load_submission(self, submission_id: str) -> SubmittedFiling:
        """Load a historical :class:`SubmittedFiling` by id.

        Args:
            submission_id: Stable submission identifier.

        Returns:
            The persisted :class:`SubmittedFiling` record.

        Raises:
            SubmissionError: If ``submission_id`` is malformed or no
                file exists at the resolved path.
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
        """Return historical persisted records, optionally filtered.

        Args:
            modelo: Optional AEAT modelo identifier to filter by
                (``filing.modelo == modelo``).
            status: Optional :class:`SubmissionStatus` to filter by.

        Returns:
            A chronologically reverse-sorted tuple of
            :class:`SubmittedFiling` records. Returns an empty tuple
            when the submissions directory does not yet exist.
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
