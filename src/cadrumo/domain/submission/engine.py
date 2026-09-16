"""Read-only submission record loader and preflight engine.

Exposes :class:`SubmissionEngine`, the only sanctioned surface for
running preflight gates and reading historical
:class:`cadrumo.domain.submission.ModeloPresentado` records persisted under
the secure SQL object backend.

AEAT remote writes and write-shaped portal walks are permanently
forbidden; the engine intentionally exposes no transport method.

See Also:
    :class:`~cadrumo.domain.submission.Preflight`
        Ordered draft, finding, deadline-window, and auth-provider gate runner
        delegated to by :meth:`SubmissionEngine.preflight`.
    :class:`~cadrumo.domain.submission.DeadlineWindowChecker`
        Injected protocol that answers the filing-window question without
        coupling this domain package to the deadline engine implementation.
    the application workflow submission protocol
        Application workflow wrapper that invokes this read-only preflight
        surface from the ``RUNNING_PREFLIGHT`` stage.
    :mod:`cadrumo.application.modelo.workflow_gate`
        Modelo work-unit bridge that configures the deadline-window checker for
        calculation revisions before verification or local mark-as-filed paths.
"""

from __future__ import annotations

from datetime import date

from ...core.config import Settings
from ...core.logging import get_logger
from .preflight import Preflight
from .protocols import AuthProviderProbe, DeadlineWindowChecker, ModeloDraftLike, SubmissionRepositoryProtocol

_logger = get_logger(__name__)


class SubmissionEngine:
    """Runs preflight and reads historical submission records.

    AEAT remote writes and write-shaped portal walks are permanently
    forbidden. This class intentionally exposes no transport method.

    Attributes:
        auth_provider: Narrow auth-provider probe used by preflight.
        deadline_checker: Narrow window checker used by preflight.
        settings: Resolved :class:`cadrumo.core.config.Settings`.
    """

    def __init__(
        self,
        *,
        auth_provider: AuthProviderProbe,
        deadline_checker: DeadlineWindowChecker,
        settings: Settings,
        repository: SubmissionRepositoryProtocol,
    ) -> None:
        """Construct a read-only :class:`SubmissionEngine`.

        Args:
            auth_provider: Narrow probe over the active auth provider.
            deadline_checker: Narrow window checker over
                :mod:`cadrumo.domain.deadlines`.
            settings: Resolved :class:`cadrumo.core.config.Settings`.
            repository: Injected :class:`SubmissionRepositoryProtocol` over the
                encrypted submission-records store; the application layer
                constructs the concrete adapter repository and passes it in.
        """
        self.auth_provider = auth_provider
        self.deadline_checker = deadline_checker
        self.settings = settings
        self._repository = repository
        self._preflight = Preflight(
            deadline_checker=deadline_checker,
            auth_provider=auth_provider,
        )

    def preflight(
        self,
        draft: ModeloDraftLike,
        *,
        today: date,
        skip_deadline_window: bool = False,
        skip_auth_readiness: bool = False,
    ) -> None:
        """Run preflight gates without browser work or AEAT writes.

        Args:
            draft: Draft conforming to :class:`ModeloDraftLike`.
            today: Calendar date used to evaluate the AEAT filing window.
            skip_deadline_window: When ``True``, the AEAT filing-window
                gate is skipped. Workflow callers use this for local
                verification and local mark-as-filed paths; callers that
                perform an actual AEAT submission must leave the gate
                enabled.
            skip_auth_readiness: When ``True``, the auth-provider
                readiness gate is skipped. Local build/verify/file/export
                purposes pass this; only live/AEAT-touching callers leave
                it enabled.
        """
        self._preflight.check(
            draft,
            today=today,
            skip_deadline_window=skip_deadline_window,
            skip_auth_readiness=skip_auth_readiness,
        )
