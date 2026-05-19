"""Domain exception hierarchy and public error-registry surface.

Every subpackage should raise subclasses of :class:`AeatError` to ensure
predictable error handling throughout the application.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from aeat.adapters.outbound.aeat.browser._site_health import SiteHealthStatus


class AeatError(Exception):
    """Base exception for all AEAT domain errors."""

    code: ClassVar[ErrorCode]

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Bind a registered :class:`ErrorCode` to each declared subclass."""

        super().__init_subclass__(**kwargs)
        from ._registry import bind_error_code

        bind_error_code(cls)

    def __init__(
        self,
        message: str | None = None,
        *,
        context: Mapping[str, object] | None = None,
        suggestion: str | None = None,
        translated_message: str | None = None,
    ) -> None:
        """Construct a domain error with optional structured metadata.

        Args:
            message: Optional human-readable message override.
            context: Optional structured context that can be redacted and
                emitted in the JSON envelope.
            suggestion: Optional copy-paste recovery command override.
            translated_message: Optional multilingual message override.
        """

        if message is None:
            super().__init__()
        else:
            super().__init__(message)
        self.context: dict[str, object] | None = dict(context) if context is not None else None
        self.suggestion: str | None = suggestion
        self.translated_message: str | None = translated_message


class CoreError(AeatError):
    """Base error for internal framework and core-primitive failures."""


class CoreValidationError(CoreError, ValueError):
    """Raised when core primitives or configuration violate invariants.

    Inherits from ValueError to maintain compatibility with Pydantic
    validators.
    """


class AeatObservabilityError(AeatError):
    """Base class for observability-layer errors.

    Lives in :mod:`aeat.core.errors` (rather than the leaf
    :mod:`aeat.core.observability` subpackage) so other subpackages can
    catch it without importing observability internals. Concrete
    subclasses are declared in :mod:`aeat.core.observability._errors`.
    """


class FixtureProvisioningError(AeatError):
    """Raised when Google Workspace test-fixture provisioning fails.

    Thrown by the provisioning and teardown scripts under ``scripts/``
    whenever a Drive / Sheets / Docs call cannot satisfy the catalogued
    intent (missing parent, quota exhausted, unexpected dedup result, etc).
    """


class ModeloFixtureError(AeatError):
    """Raised when a synthetic modelo-history fixture cannot be loaded.

    Thrown by :mod:`aeat.application.filing.testing` when the fixtures directory cannot be
    resolved, a fixture file cannot be read, JSON decoding fails, or a
    payload fails strict pydantic validation (including the synthetic-
    only invariant checks on the ``synthetic`` and ``_comment`` fields).
    """


class SiteHealthError(AeatError):
    """Raised when AEAT site-health detection classifies a non-OK state.

    Carries a strict :class:`aeat.adapters.outbound.aeat.browser._site_health.SiteHealthStatus`
    attribute describing the detected state (mantenimiento, WAF challenge,
    rate limit, unreachable, unknown error) together with the evidence
    used to classify it. The workflow engine catches this error in a typed
    arm that precedes the generic exception handler so a planned
    mantenimiento never collapses into ``UNHANDLED_EXCEPTION``.

    The error lives in :mod:`aeat.core.errors` (and not in either leaf
    subpackage) to break the circular import between
    :mod:`aeat.adapters.outbound.aeat.browser` (which raises it) and :mod:`aeat.application.workflow`
    (which consumes it).

    The ``SiteHealthStatus`` import is guarded by ``TYPE_CHECKING`` so no
    runtime adapter-layer import occurs; :data:`.importlinter` is configured
    with ``exclude_type_checking_imports = True`` to keep this edge invisible
    to the ``core-not-outer`` contract.
    """

    def __init__(self, *, status: SiteHealthStatus) -> None:
        """Construct a SiteHealthError carrying a detected status.

        Args:
            status: The strict
                :class:`aeat.adapters.outbound.aeat.browser._site_health.SiteHealthStatus`
                instance describing the detected non-OK state.
        """

        state = status.state
        state_value = getattr(state, "value", state)
        evidence = status.evidence
        context: dict[str, object] = {
            "state": str(state_value),
            "url": str(evidence.url),
            "http_status": evidence.http_status,
            "detected_markers": tuple(evidence.detected_markers),
            "observed_at": status.observed_at.isoformat(),
        }
        if status.retry_after_seconds is not None:
            context["retry_after_seconds"] = status.retry_after_seconds
        super().__init__(str(state_value), context=context)
        self.status: SiteHealthStatus = status


class McpLaunchError(AeatError):
    """Raised when a repo-managed MCP process cannot be launched safely."""


from ._registry import (
    ERROR_REGISTRY,
    ErrorCategory,
    ErrorCode,
    ErrorEnvelope,
    bind_error_code,
    build_error_envelope,
    get_error_exit_code,
    get_registered_error_code,
    register,
    render_error_json,
    render_error_text,
    resolve_error_message,
    resolve_output_language,
    scrub_error_context,
)
from ._severity import BaseSeverity

__all__ = [
    "ERROR_REGISTRY",
    "AeatError",
    "AeatObservabilityError",
    "BaseSeverity",
    "CoreError",
    "CoreValidationError",
    "ErrorCategory",
    "ErrorCode",
    "ErrorEnvelope",
    "ModeloFixtureError",
    "FixtureProvisioningError",
    "McpLaunchError",
    "SiteHealthError",
    "bind_error_code",
    "build_error_envelope",
    "get_error_exit_code",
    "get_registered_error_code",
    "register",
    "render_error_json",
    "render_error_text",
    "resolve_error_message",
    "resolve_output_language",
    "scrub_error_context",
]
