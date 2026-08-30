"""Exception hierarchy for :mod:`adapters.outbound.aeat.sede`.

Defines the base :exc:`SedeError` plus the narrowly-scoped subclasses
raised by the sede navigation, parsing, and fetch helpers. Every
subclass extends :exc:`core.errors.CadrumoError` so callers can
trap the whole AEAT integration surface with a single
``except CadrumoError``.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from .....core.errors.hierarchy import CadrumoError, CoreError


class SedeError(CadrumoError):
    """Base class for post-auth AEAT sede errors.

    Extends :exc:`core.errors.CadrumoError` so callers tracking
    cross-package errors can catch the whole AEAT surface uniformly.
    """

    def __init__(
        self,
        message: str | None = None,
        *,
        failure_mode: SedeFailureMode | str | None = None,
        context: Mapping[str, object] | None = None,
        translated_message: str | None = None,
    ) -> None:
        """Construct a Sede error with optional stable failure-mode context."""
        enriched_context = dict(context) if context is not None else {}
        if failure_mode is not None:
            failure_mode_value = failure_mode.value if isinstance(failure_mode, SedeFailureMode) else str(failure_mode)
            enriched_context["failure_mode"] = failure_mode_value
            self.failure_mode: str | None = failure_mode_value
        else:
            self.failure_mode = None
        super().__init__(
            message,
            context=enriched_context or None,
            translated_message=translated_message,
        )


class SedeFailureMode(StrEnum):
    """Closed post-auth Sede failure modes surfaced by live browser adapters."""

    LIVE_NAVIGATION_FAILED = "live_navigation_failed"
    SITE_HEALTH_FAILED = "site_health_failed"
    BROWSER_BACKEND_FAILED = "browser_backend_failed"
    EXTERNAL_SHAPE_CHANGED = "external_shape_changed"
    # Surface that requires AEAT authentication (cl@ve / certificate)
    # which the live driver does not hold. The form navigation succeeds
    # at HTTP 200 but redirects to AEAT's standard 4033 / 403 error page.
    AUTH_GATE_DETECTED = "auth_gate_detected"


class SedeNavigationError(SedeError):
    """Raised when a navigation step fails (goto, click, wait)."""


class SedeParseError(SedeError):
    """Raised when the captured HTML cannot be parsed to a record."""


class ExpedienteNotFoundError(SedeError):
    """Raised when no expediente matches the requested filter."""


class JustificanteFetchError(SedeError):
    """Raised when the CSV-keyed PDF download fails or is malformed."""


class SedeValidationError(SedeError, ValueError):
    """Raised when data captured from Sede violates expected shape or invariants.

    Inherits from ValueError to maintain compatibility with Pydantic
    validators.
    """


class BrowserAdapterTypeError(CoreError):
    """Raised when ``BrowserContext.new_page()`` returns an unexpected type.

    All three sede live-adapter entry points (Renta WEB Open, NIF-IVA check,
    GROI check) guard the ``BrowserContext.new_page()`` return value against
    Playwright version skew or mock-adapter misuse. This shared error class
    replaces the three bare ``TypeError`` raises so callers can catch a typed,
    registered envelope instead of the built-in exception.
    """


__all__ = [
    "BrowserAdapterTypeError",
    "ExpedienteNotFoundError",
    "JustificanteFetchError",
    "SedeError",
    "SedeFailureMode",
    "SedeNavigationError",
    "SedeParseError",
    "SedeValidationError",
]
