"""Preflight gating for the filing submission engine.

``Preflight`` runs four ordered gates against a
:class:`aeat.domain.submission._protocols.ModeloDraftLike` before any
browser work begins. Every failure raises
:class:`SubmissionPreflightError`; the happy path is silent.
"""

from __future__ import annotations

from datetime import date

from ...core.errors import AeatError
from ...core.logging import get_logger
from ._errors import SubmissionPreflightError
from ._protocols import (
    AuthProviderDescriptionLike,
    AuthProviderProbe,
    DeadlineWindowChecker,
    ModeloDraftLike,
    ModeloDraftStatus,
)

_logger = get_logger(__name__)


# StrEnum value for ``AuthProviderKind.CERTIFICATE`` — duplicated as a
# bare string so the domain layer does not import the application-layer
# enum at runtime. Kept in sync with
# :class:`aeat.application.auth.AuthProviderKind` by code review.
_AUTH_KIND_CERTIFICATE = "certificate"
_PREFLIGHT_DRAFT_STALE_LOCALE_KEY = "errors.refused.submission_preflight_draft_stale"
_PREFLIGHT_DRAFT_NOT_APPROVED_LOCALE_KEY = "errors.refused.submission_preflight_draft_not_approved"
_PREFLIGHT_ERROR_FINDINGS_LOCALE_KEY = "errors.refused.submission_preflight_error_findings"
_PREFLIGHT_DEADLINE_CLOSED_LOCALE_KEY = "errors.refused.submission_preflight_deadline_closed"
_PREFLIGHT_AUTH_DESCRIBE_FAILED_LOCALE_KEY = "errors.refused.submission_preflight_auth_describe_failed"
_PREFLIGHT_AUTH_NOT_READY_LOCALE_KEY = "errors.refused.submission_preflight_auth_not_ready"


def _describe_provider_operator_impact(description: AuthProviderDescriptionLike) -> str:
    """Return the operator-impact summary for ``description``.

    Mirror of
    :func:`aeat.application.auth.describe_provider_operator_impact`.
    Duplicated here because the layered-import contract forbids
    `aeat.domain.*` from depending on `aeat.application.*` at runtime;
    the helper is pure string formatting against ``description``'s
    pydantic fields, so co-locating it with the gate that consumes
    its output keeps the domain leaf clean.
    """
    if not description.configured:
        return (
            "operator can still produce, verify, and export filings locally, but "
            "AEAT-backed reads stay unavailable until an auth "
            "provider is configured."
        )
    if not description.available:
        return (
            f"{description.label} is configured but not ready yet. operator can still "
            "produce, verify, and export filings locally, but AEAT-backed reads "
            "stay unavailable until auth is fixed."
        )
    if _enum_value(description.kind) == _AUTH_KIND_CERTIFICATE:
        return (
            "Certificate auth is ready. operator keeps the same CLI filing flow for "
            "AEAT-backed reads, and future providers can plug into the same "
            "commands without changing the workflow."
        )
    return (
        f"{description.label} is ready. operator keeps the same CLI filing flow while "
        "this provider plugs into the shared auth protocol."
    )


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
    ) -> None:
        """Run the four preflight gates against ``draft``.

        Args:
            draft: The :class:`ModeloDraftLike` to validate.
            today: Reference date for the deadline-window gate.
            skip_deadline_window: When ``True``, gate 3 (the AEAT
                filing-window check) is skipped. Verification of a
                calculation is independent of the filing calendar (see
                the work-verify deadline-independence ADR): the verify
                path runs gates 1, 2, and 4 to confirm the draft is
                sound but must not refuse because the filing window is
                closed or absent. Filing always runs gate 3.

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

        error_findings = tuple(f for f in draft.findings if _enum_value(getattr(f, "severity", None)) == "error")
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

        try:
            description = self.auth_provider.describe()
        except AeatError as exc:
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
                    "operator_impact": _describe_provider_operator_impact(description),
                },
            )
        _logger.debug(
            "preflight gate-4 ok: auth provider ready (kind=%s expires_on=%s)",
            description.kind,
            description.expires_on,
        )


def _enum_value(value: object) -> str:
    """Return ``Enum.value`` when present, otherwise ``str(value)``."""
    if value is None:
        return ""
    raw = getattr(value, "value", value)
    return str(raw)
