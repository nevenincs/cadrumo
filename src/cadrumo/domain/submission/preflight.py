"""Preflight gating for the filing submission engine.

``Preflight`` runs four ordered gates against a
:class:`cadrumo.domain.submission.protocols.ModeloDraftLike` before any
browser work begins. Every failure raises
:class:`SubmissionPreflightError`; the happy path is silent.

See Also:
    :class:`~cadrumo.domain.submission.SubmissionEngine`
        Public read-only engine that owns this preflight runner.
    :class:`~cadrumo.domain.submission.DeadlineWindowChecker`
        Gate-3 protocol used only when the caller has not skipped the filing
        window check.
    :class:`~cadrumo.application.workflow.WorkflowPurpose`
        Application policy input that decides whether workflow callers pass
        ``skip_deadline_window`` for local verification or filing.
"""

from __future__ import annotations

from datetime import date

from ...core.errors.hierarchy import CadrumoError
from ...core.errors.severity import BaseSeverity
from ...core.i18n import describe_auth_provider_operator_impact
from ...core.logging import get_logger
from ...core.parsing import enum_value as _enum_value
from .errors import SubmissionPreflightError
from .models import ModeloDraftStatus
from .protocols import AuthProviderProbe, DeadlineWindowChecker, ModeloDraftLike

_logger = get_logger(__name__)


_PREFLIGHT_DRAFT_STALE_LOCALE_KEY = "errors.refused.submission_preflight_draft_stale"
_PREFLIGHT_DRAFT_NOT_APPROVED_LOCALE_KEY = "errors.refused.submission_preflight_draft_not_approved"
_PREFLIGHT_ERROR_FINDINGS_LOCALE_KEY = "errors.refused.submission_preflight_error_findings"
_PREFLIGHT_DEADLINE_CLOSED_LOCALE_KEY = "errors.refused.submission_preflight_deadline_closed"
_PREFLIGHT_AUTH_DESCRIBE_FAILED_LOCALE_KEY = "errors.refused.submission_preflight_auth_describe_failed"
_PREFLIGHT_AUTH_NOT_READY_LOCALE_KEY = "errors.refused.submission_preflight_auth_not_ready"


class Preflight:
    """Four-gate validator for a :class:`ModeloDraftLike`.

    Gates run in order:

    1. Draft status is :attr:`ModeloDraftStatus.APROBADO`.
    2. No ``ERROR``-severity entries in ``draft.findings``.
    3. Deadline window is open via
       :meth:`DeadlineWindowChecker.is_window_open`.
    4. Auth provider describes itself cleanly via :meth:`AuthProviderProbe.describe`.

    The validator is pure: no I/O beyond the injected Protocol calls,
    no state beyond its dependencies.

    Attributes:
        deadline_checker: Protocol implementation used for gate 3.
        auth_provider: Protocol implementation used for gate 4.
    """

    def __init__(
        self,
        *,
        deadline_checker: DeadlineWindowChecker,
        auth_provider: AuthProviderProbe,
    ) -> None:
        """Construct a preflight validator.

        Args:
            deadline_checker: Protocol used for the deadline-window gate.
            auth_provider: Protocol used for the auth-provider gate.
        """
        self.deadline_checker = deadline_checker
        self.auth_provider = auth_provider

    def check(
        self,
        draft: ModeloDraftLike,
        *,
        today: date,
        skip_deadline_window: bool = False,
        skip_auth_readiness: bool = False,
    ) -> None:
        """Run the four preflight gates against ``draft``.

        Args:
            draft: The :class:`ModeloDraftLike` to validate.
            today: Reference date for the deadline-window gate.
            skip_deadline_window: When ``True``, gate 3 (the AEAT
                filing-window check) is skipped. Workflow callers use
                this for local VERIFY and local FILE purposes: the
                redundant AEAT submission-window check remains disabled
                for paths that do not submit to AEAT.
            skip_auth_readiness: When ``True``, gate 4 (auth-provider
                readiness) is skipped. Auth binds only live/AEAT-touching
                purposes (pull, reconcile, a live session): the whole
                local artefact flow — build, calculate, VERIFY, local
                FILE, export — completes with no auth provider configured,
                because the human uploads at the AEAT portal themselves.
                Callers that perform an actual AEAT read/submission leave
                the gate enabled (the default).

        Raises:
            SubmissionPreflightError: If any gate fails. The exception
                message identifies the failing gate.
        """
        _logger.debug(
            "preflight start: draft_id=%s modelo=%s period=%s",
            draft.draft_id,
            draft.modelo,
            draft.period,
        )

        status_value = _enum_value(draft.status)
        if status_value != ModeloDraftStatus.APROBADO.value:
            _logger.debug("preflight gate-1 fail: draft status=%s", draft.status)
            if status_value == ModeloDraftStatus.APROBACION_CADUCADA.value:
                raise SubmissionPreflightError(
                    "draft approval is stale",
                    translated_message=_PREFLIGHT_DRAFT_STALE_LOCALE_KEY,
                    context={"status": status_value},
                )
            raise SubmissionPreflightError(
                "draft not approved for submission",
                translated_message=_PREFLIGHT_DRAFT_NOT_APPROVED_LOCALE_KEY,
                context={"status": status_value},
            )
        _logger.debug("preflight gate-1 ok: draft is approved")

        # Read through the typed ``ModeloFindingLike`` port (``.severity`` is
        # a REQUIRED field on both real implementations) rather than
        # ``getattr(f, "severity", None)``: a future rename of the field
        # must fail loud here, not silently exclude every finding -- error
        # severity included -- from the gate whose entire job is blocking
        # submission on them.
        error_findings = tuple(f for f in draft.findings if f.severity == BaseSeverity.ERROR)
        if error_findings:
            _logger.debug(
                "preflight gate-2 fail: %d error-severity findings",
                len(error_findings),
            )
            raise SubmissionPreflightError(
                "draft has error-severity findings",
                translated_message=_PREFLIGHT_ERROR_FINDINGS_LOCALE_KEY,
                context={"finding_count": len(error_findings)},
            )
        _logger.debug("preflight gate-2 ok: no error findings")

        if skip_deadline_window:
            _logger.debug("preflight gate-3 skipped: verification is independent of the filing window")
        elif not self.deadline_checker.is_window_open(draft.modelo, draft.period, today):
            _logger.debug(
                "preflight gate-3 fail: deadline window closed for %s %s on %s",
                draft.modelo,
                draft.period,
                today,
            )
            raise SubmissionPreflightError(
                "deadline window is closed",
                translated_message=_PREFLIGHT_DEADLINE_CLOSED_LOCALE_KEY,
                context={"modelo": draft.modelo, "period": str(draft.period), "today": today.isoformat()},
            )
        else:
            _logger.debug("preflight gate-3 ok: deadline window is open")

        if skip_auth_readiness:
            _logger.debug(
                "preflight gate-4 skipped: auth-provider readiness binds only "
                "live/AEAT-touching purposes, not the local build/verify/file/export flow",
            )
            return

        try:
            description = self.auth_provider.describe()
        except CadrumoError as exc:
            _logger.warning("preflight gate-4 fail: auth provider describe raised", exc_info=True)
            raise SubmissionPreflightError(
                "auth provider failed to describe itself",
                translated_message=_PREFLIGHT_AUTH_DESCRIBE_FAILED_LOCALE_KEY,
                context={"cause_type": type(exc).__name__},
            ) from exc
        if not description.configured or not description.available:
            _logger.debug(
                "preflight gate-4 fail: auth provider unavailable kind=%s configured=%s available=%s",
                description.kind,
                description.configured,
                description.available,
            )
            raise SubmissionPreflightError(
                "auth provider is not ready",
                translated_message=_PREFLIGHT_AUTH_NOT_READY_LOCALE_KEY,
                context={
                    "kind": _enum_value(description.kind),
                    "configured": description.configured,
                    "available": description.available,
                    "operator_impact": describe_auth_provider_operator_impact(description),
                },
            )
        _logger.debug(
            "preflight gate-4 ok: auth provider ready (kind=%s expires_on=%s)",
            description.kind,
            description.expires_on,
        )
