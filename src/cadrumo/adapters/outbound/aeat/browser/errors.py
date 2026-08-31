"""Shared exception types for AEAT browser adapters.

The browser adapter wraps Playwright launch, context creation, evasion,
navigation, site-health, and teardown failures in :class:`BrowserError` with a
stable :class:`BrowserFailureMode`. That mode is copied into the structured
``context`` mapping so CLI and workflow error renderers can classify failures
without parsing message text.

See Also:
    :class:`adapters.outbound.aeat.browser.BrowserSession`
        Central owner that emits these browser errors.
    :class:`adapters.outbound.aeat.browser.EvasionStrategy`
        Strategy hook whose setup failures surface as :class:`BrowserEvasionError`.
    :class:`adapters.outbound.aeat.browser.SiteHealthStatus`
        Site-health record carried separately by
        :class:`core.errors.SiteHealthError` when AEAT itself returns a
        classified non-OK response.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from .....application.operator_actions.models import PreconditionVerdict
from .....application.operator_actions.preconditions import no_action_precondition_verdict
from .....core.errors.hierarchy import CadrumoError, TerminalPreconditionErrorMixin
from .....core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome


class BrowserPreconditionCondition(StrEnum):
    """Stable failed conditions observed at the AEAT browser boundary."""

    OPTIONAL_EXTRA_AVAILABLE = "aeat.browser.optional_extra.available"
    RUNTIME_STARTABLE = "aeat.browser.runtime.startable"
    RUNTIME_STOPPABLE = "aeat.browser.runtime.stoppable"
    SESSION_AVAILABLE = "aeat.browser.session.available"
    BROWSER_LAUNCHABLE = "aeat.browser.launchable"
    CONTEXT_CREATABLE = "aeat.browser.context.creatable"
    EVASION_SUPPORT_AVAILABLE = "aeat.browser.evasion_support.available"
    EVASION_APPLIED = "aeat.browser.evasion.applied"
    PAGE_CONTENT_READABLE = "aeat.browser.page_content.readable"
    BROWSER_CLOSEABLE = "aeat.browser.closeable"


def browser_no_action_verdict(
    *,
    condition: BrowserPreconditionCondition,
    facts: Mapping[str, str | int | bool],
    outcome: NoRecoveryOutcome,
):
    """Delegate one fact-only browser refusal to the public verdict authority."""
    return no_action_precondition_verdict(
        condition_id=condition.value,
        facts=facts,
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=outcome,
    )


class BrowserError(TerminalPreconditionErrorMixin[PreconditionVerdict], CadrumoError):
    """Base class for browser-related failures.

    ``failure_mode`` may be a :class:`BrowserFailureMode` member or an existing
    string value. When supplied, it is stored both on ``self.failure_mode`` and
    under ``context["failure_mode"]`` so downstream callers can branch on one
    stable tag.
    """

    def __init__(
        self,
        message: str | None = None,
        *,
        failure_mode: BrowserFailureMode | str | None = None,
        context: Mapping[str, object] | None = None,
        translated_message: str | None = None,
        precondition_verdict: PreconditionVerdict | None = None,
    ) -> None:
        """Construct a browser error with an optional failure-mode tag."""
        enriched_context = dict(context) if context is not None else {}
        if failure_mode is not None:
            failure_mode_value = (
                failure_mode.value if isinstance(failure_mode, BrowserFailureMode) else str(failure_mode)
            )
            enriched_context["failure_mode"] = failure_mode_value
            self.failure_mode: str | None = failure_mode_value
        else:
            self.failure_mode = None
        super().__init__(
            message,
            context=enriched_context or None,
            translated_message=translated_message,
            precondition_verdict=precondition_verdict,
        )


class BrowserValidationError(BrowserError, ValueError):
    """Raised when browser parameters or field values fail domain validation.

    This error inherits from both :class:`BrowserError` and :class:`ValueError`,
    ensuring compatibility with Pydantic's validator contract while
    remaining catchable under the package's unified error hierarchy.
    """


class BrowserEvasionError(BrowserError):
    """Raised when browser evasion setup cannot be applied.

    :class:`PlaywrightStealthEvasion <adapters.outbound.aeat.browser.PlaywrightStealthEvasion>`
    raises this when ``playwright-stealth`` is unavailable. Failures that occur
    while :class:`BrowserSession <adapters.outbound.aeat.browser.BrowserSession>`
    applies any strategy are wrapped with
    :attr:`BrowserFailureMode.EVASION_FAILED`.
    """


class BrowserFailureMode(StrEnum):
    """Closed browser-backend failure modes emitted by the central session.

    :class:`BrowserSession <adapters.outbound.aeat.browser.BrowserSession>`
    uses these values for one-live-context enforcement, browser launch,
    context creation, evasion, page-content reads, navigation transport
    failures, site-health classifications, and retained browser close
    failures.
    """

    SESSION_BUSY = "session_busy"
    OPTIONAL_EXTRA_UNAVAILABLE = "optional_extra_unavailable"
    PLAYWRIGHT_RUNTIME_START_FAILED = "playwright_runtime_start_failed"
    PLAYWRIGHT_RUNTIME_STOP_FAILED = "playwright_runtime_stop_failed"
    BROWSER_LAUNCH_FAILED = "browser_launch_failed"
    CONTEXT_CREATE_FAILED = "context_create_failed"
    EVASION_FAILED = "evasion_failed"
    PAGE_CONTENT_FAILED = "page_content_failed"
    NAVIGATION_TIMEOUT = "navigation_timeout"
    NAVIGATION_TRANSPORT_ERROR = "navigation_transport_error"
    SITE_HEALTH_NON_OK = "site_health_non_ok"
    BROWSER_CLOSE_FAILED = "browser_close_failed"
