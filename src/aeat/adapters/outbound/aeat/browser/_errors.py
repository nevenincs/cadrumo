"""Shared exception types for AEAT browser adapters."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from .....core.errors import AeatError


class BrowserError(AeatError):
    """Base class for browser-related errors."""

    def __init__(
        self,
        message: str | None = None,
        *,
        failure_mode: BrowserFailureMode | str | None = None,
        context: Mapping[str, object] | None = None,
        suggestion: str | None = None,
        translated_message: str | None = None,
    ) -> None:
        """Construct a browser error with a stable failure-mode tag."""
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
    """Raised when browser evasion setup cannot be applied."""


class BrowserFailureMode(StrEnum):
    """Closed browser-backend failure modes emitted by the central session."""

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
