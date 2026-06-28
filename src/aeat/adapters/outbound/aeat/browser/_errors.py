"""Shared exception types for AEAT browser adapters.

The browser adapter wraps Playwright launch, context creation, evasion,
navigation, site-health, and teardown failures in :class:`BrowserError` with a
stable :class:`BrowserFailureMode`. That mode is copied into the structured
``context`` mapping so CLI and workflow error renderers can classify failures
without parsing message text.

See Also:
    :class:`aeat.adapters.outbound.aeat.browser.BrowserSession`
        Central owner that emits these browser errors.
    :class:`aeat.adapters.outbound.aeat.browser.EvasionStrategy`
        Strategy hook whose setup failures surface as :class:`BrowserEvasionError`.
    :class:`aeat.adapters.outbound.aeat.browser.SiteHealthStatus`
        Site-health record carried separately by
        :class:`aeat.core.errors.SiteHealthError` when AEAT itself returns a
        classified non-OK response.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from .....core.errors import AeatError


class BrowserError(AeatError):
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
        suggestion: str | None = None,
        translated_message: str | None = None,
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
            suggestion=suggestion,
            translated_message=translated_message,
        )


class BrowserValidationError(BrowserError, ValueError):
    """Raised when browser parameters or field values fail domain validation.

    This error inherits from both :class:`BrowserError` and :class:`ValueError`,
    ensuring compatibility with Pydantic's validator contract while
    remaining catchable under the package's unified error hierarchy.
    """


class BrowserEvasionError(BrowserError):
    """Raised when browser evasion setup cannot be applied.

    :class:`PlaywrightStealthEvasion <aeat.adapters.outbound.aeat.browser.PlaywrightStealthEvasion>`
    raises this when ``playwright-stealth`` is unavailable. Failures that occur
    while :class:`BrowserSession <aeat.adapters.outbound.aeat.browser.BrowserSession>`
    applies any strategy are wrapped with
    :attr:`BrowserFailureMode.EVASION_FAILED`.
    """


class BrowserFailureMode(StrEnum):
    """Closed browser-backend failure modes emitted by the central session.

    :class:`BrowserSession <aeat.adapters.outbound.aeat.browser.BrowserSession>`
    uses these values for one-live-context enforcement, browser launch,
    context creation, evasion, provider annotation, page-content reads,
    navigation transport failures, site-health classifications, and retained
    browser close failures.
    """

    SESSION_BUSY = "session_busy"
    BROWSER_LAUNCH_FAILED = "browser_launch_failed"
    CONTEXT_CREATE_FAILED = "context_create_failed"
    EVASION_FAILED = "evasion_failed"
    CONTEXT_ANNOTATION_FAILED = "context_annotation_failed"
    PAGE_CONTENT_FAILED = "page_content_failed"
    NAVIGATION_TIMEOUT = "navigation_timeout"
    NAVIGATION_TRANSPORT_ERROR = "navigation_transport_error"
    SITE_HEALTH_NON_OK = "site_health_non_ok"
    BROWSER_CLOSE_FAILED = "browser_close_failed"
