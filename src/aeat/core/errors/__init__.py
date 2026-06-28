"""Domain exception hierarchy and public error-registry surface.

Every subpackage should raise subclasses of :class:`AeatError` to ensure
predictable error handling throughout the application.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import ClassVar, Protocol, runtime_checkable


@runtime_checkable
class SiteHealthEvidenceLike(Protocol):
    """Structural view of the evidence block carried by a site-health status.

    Declared in :mod:`aeat.core.errors` so :class:`SiteHealthError` can
    type its payload without importing the adapter layer that produces
    it. The concrete record is
    :class:`aeat.adapters.outbound.aeat.browser._site_health.SiteHealthEvidence`.

    Members are read-only properties so the protocol matches
    covariantly: a concrete record may carry narrower member types
    (e.g. ``AnyHttpUrl`` for ``url``) and still satisfy the structural
    view, which a mutable attribute declaration would reject.
    """

    @property
    def url(self) -> object:
        """URL that was probed during the health check."""
        ...

    @property
    def http_status(self) -> object:
        """HTTP status code returned by the probed URL."""
        ...

    @property
    def detected_markers(self) -> Sequence[object]:
        """Sequence of markers detected in the response that triggered classification."""
        ...


@runtime_checkable
class SiteHealthStatusLike(Protocol):
    """Structural view of a detected AEAT site-health classification.

    Declared in :mod:`aeat.core.errors` so :class:`SiteHealthError` can
    accept the status without a runtime or type-checking import of the
    adapter layer. The concrete record is
    :class:`aeat.adapters.outbound.aeat.browser._site_health.SiteHealthStatus`.

    Members are read-only properties so the protocol matches
    covariantly: the concrete ``SiteHealthStatus`` carries a concrete
    ``SiteHealthEvidence`` for ``evidence``, which satisfies the
    ``SiteHealthEvidenceLike`` view only when the member is read-only.
    """

    @property
    def state(self) -> object:
        """Classified site-health state (e.g. mantenimiento, WAF challenge, rate limit)."""
        ...

    @property
    def evidence(self) -> SiteHealthEvidenceLike:
        """Evidence block used to classify the detected state.

        Returns a :class:`SiteHealthEvidenceLike` carrying the URL,
        HTTP status, and detected markers that drove classification.
        """
        ...

    @property
    def observed_at(self) -> datetime:
        """Timestamp at which the health check observation was recorded."""
        ...

    @property
    def retry_after_seconds(self) -> int | None:
        """Suggested retry delay in seconds, or ``None`` when not provided."""
        ...


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


class DecimalFormatError(CoreError):
    """Raised when :func:`~aeat.core.decimal._format.format_decimal` receives an invalid argument.

    Replaces the bare :class:`TypeError` previously raised when ``value``
    is ``None`` but ``none_value`` was not provided.
    """


class RedactionError(CoreError):
    """Raised when a redaction helper receives an argument of the wrong type.

    Replaces bare :class:`TypeError` previously raised by
    :func:`~aeat.core.redaction.redact` and
    :func:`~aeat.core.redaction.redact_for_cli_output` when passed a
    non-``str`` argument.
    """


class CoreValidationError(CoreError, ValueError):
    """Raised when core primitives or configuration violate invariants.

    Inherits from ValueError to maintain compatibility with Pydantic
    validators.
    """


class ProfileAnswerTypeError(CoreValidationError):
    """Raised when a typed profile-answers field coercion receives an unexpected type.

    Lives in :mod:`aeat.core.errors` so :class:`~aeat.core.setup_answers.SetupAnswers`
    can raise a typed error without importing application-layer wizard modules.
    Application-layer wizard code raises the narrower
    :class:`~aeat.application.wizard._errors.WizardAnswerTypeError`, which
    inherits from this class, so callers catching either type continue to work.
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

    Carries a :class:`SiteHealthStatusLike` payload describing the
    detected state (mantenimiento, WAF challenge, rate limit,
    unreachable, unknown error) together with the evidence used to
    classify it. The workflow engine catches this error in a typed arm
    that precedes the generic exception handler so a planned
    mantenimiento never collapses into ``UNHANDLED_EXCEPTION``.

    The error lives in :mod:`aeat.core.errors` (and not in either leaf
    subpackage) to break the circular import between
    :mod:`aeat.adapters.outbound.aeat.browser` (which raises it) and
    :mod:`aeat.application.workflow` (which consumes it). The payload is
    typed through the :class:`SiteHealthStatusLike` structural Protocol
    declared in this module, so no import of the adapter layer occurs at
    runtime or under type checking — the ``core-not-outer`` boundary is
    satisfied without an exclusion.
    """

    def __init__(self, *, status: SiteHealthStatusLike) -> None:
        """Construct a SiteHealthError carrying a detected status.

        Args:
            status: A :class:`SiteHealthStatusLike` instance describing
                the detected non-OK state. The concrete record is the
                adapter-layer ``SiteHealthStatus``.
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
        self.status: SiteHealthStatusLike = status


class McpLaunchError(AeatError):
    """Raised when a repo-managed MCP process cannot be launched safely."""


class ActiveProfilePointerError(CoreError):
    """Raised when the active-profile pointer is present but invalid.

    A missing pointer is a clean cold-start state. A present pointer that
    cannot be parsed, decoded, read, or validated is storage metadata
    corruption and must not degrade to a root fallback database route.
    """

    def __init__(self, *, path: object) -> None:
        """Construct the active-profile pointer integrity error.

        Args:
            path: Pointer file path that failed to load.
        """
        super().__init__(
            f"invalid active-profile pointer at {path}; refusing root storage fallback",
            translated_message="errors.integrity.integrity_active_profile_pointer",
            context={"path": str(path)},
            suggestion="aeat config repair profile",
        )


class NoActiveProfileError(AeatError):
    """Raised when an operation requires an active profile bucket and none is selected.

    Bucket-scoped repositories (transaction catalogue, manual ledger,
    bucket-local aggregation) and the operator-initiated auth/sede flows refuse
    to operate without an active profile. The active-bucket precedence chain is
    a core concern (env var > pointer file), so the refusal that gates it lives
    in the core error taxonomy and is raised by
    :func:`aeat.core.require_active_bucket_id`. Callers that surface this to the
    operator map it to the standard ``cli.common.errors.no_active_profile`` message.
    """


from ._not_found import CoreNotFoundError
from ._registry import (
    ERROR_REGISTRY,
    ErrorCategory,
    ErrorCode,
    ErrorEnvelope,
    bind_error_code,
    build_error_envelope,
    declared_error_codes,
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
    "ActiveProfilePointerError",
    "AeatError",
    "AeatObservabilityError",
    "BaseSeverity",
    "CoreError",
    "CoreNotFoundError",
    "CoreValidationError",
    "DecimalFormatError",
    "ErrorCategory",
    "ErrorCode",
    "ErrorEnvelope",
    "FixtureProvisioningError",
    "McpLaunchError",
    "ModeloFixtureError",
    "NoActiveProfileError",
    "ProfileAnswerTypeError",
    "RedactionError",
    "SiteHealthError",
    "SiteHealthEvidenceLike",
    "SiteHealthStatusLike",
    "bind_error_code",
    "build_error_envelope",
    "declared_error_codes",
    "get_error_exit_code",
    "get_registered_error_code",
    "register",
    "render_error_json",
    "render_error_text",
    "resolve_error_message",
    "resolve_output_language",
    "scrub_error_context",
]
