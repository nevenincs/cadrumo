"""Domain exception hierarchy and public error-registry surface.

Every subpackage should raise subclasses of :class:`CadrumoError` to ensure
predictable error handling throughout the application.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from typing import TYPE_CHECKING, ClassVar, Protocol, TypeVar, cast, runtime_checkable

if TYPE_CHECKING:
    from ._registry import ErrorEnvelope

VerdictT = TypeVar("VerdictT")


@runtime_checkable
class SiteHealthEvidenceLike(Protocol):
    """Structural view of the evidence block carried by a site-health status.

    Declared in :mod:`core.errors` so :class:`SiteHealthError` can
    type its payload without importing the adapter layer that produces
    it. The concrete record is
    :class:`adapters.outbound.aeat.browser._site_health.SiteHealthEvidence`.

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

    Declared in :mod:`core.errors` so :class:`SiteHealthError` can
    accept the status without a runtime or type-checking import of the
    adapter layer. The concrete record is
    :class:`adapters.outbound.aeat.browser._site_health.SiteHealthStatus`.

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


class CadrumoError(Exception):
    """Base exception for all registered Cadrumo errors."""

    __bare_base_rationale__: ClassVar[str] = "central root of the registry-bound exception hierarchy"

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
        translated_message: str | None = None,
    ) -> None:
        """Construct a domain error with optional structured metadata.

        A ``translated_message``-only construction still carries readable text:
        ``super().__init__()`` receives ``translated_message`` so ``str(exc)``
        renders it rather than the empty string. Most operator-facing surfaces
        route through :func:`resolve_error_message`, which resolves the
        translation key and is unaffected either way, but a bare ``str(exc)``
        reaches operators at several CLI boundaries and reaches everyone in
        tracebacks and logs, and an error with no readable text gives whoever
        meets it nothing to act on.

        When NEITHER ``message`` nor ``translated_message`` is given,
        ``super().__init__()`` is called with no positional argument at all,
        so ``exc.args == ()`` — never a synthetic ``("",)``. ``str(exc)`` is
        the empty string either way (Python's default ``Exception.__str__``
        renders a zero-length ``args`` and a one-element ``args`` of ``""``
        identically), so this changes only the shape of ``.args``, not any
        rendered text. That shape matters to a subclass such as
        :class:`~entrypoints.cli._tty.NonTtyRefusedError`, which constructs
        with neither argument specifically so ``args`` stays empty and the CLI
        renderer's ``error.args and error.args[0]`` check
        (:mod:`core.errors._registry`) falls through to the registry
        ``message_key`` for locale resolution rather than short-circuiting on
        a truthy-but-blank ``args[0]``.

        Args:
            message: Optional human-readable message override.
            context: Optional structured context that can be redacted and
                emitted in the JSON envelope.
            translated_message: Optional multilingual message override.
        """
        text = message or translated_message
        if text:
            super().__init__(text)
        else:
            super().__init__()
        self.context: dict[str, object] | None = dict(context) if context is not None else None
        self.translated_message: str | None = translated_message


class TerminalPreconditionErrorMixin[VerdictT]:
    """Carry one typed terminal verdict without coupling core to application models.

    The mixin deliberately stores the verdict as an opaque object: the
    application owns the concrete ``PreconditionVerdict`` record, while core
    owns this layer-neutral exception transport behavior. It is mixed in ahead
    of a registered error class so that class keeps its own error code.
    """

    def __init__(
        self,
        message: str | None = None,
        *,
        context: Mapping[str, object] | None = None,
        translated_message: str | None = None,
        precondition_verdict: VerdictT | None = None,
    ) -> None:
        """Initialize the parent error and retain its terminal verdict."""
        parent_init = cast(Callable[..., None], super().__init__)
        parent_init(message, context=context, translated_message=translated_message)
        self._terminal_precondition_verdict = precondition_verdict

    @property
    def terminal_precondition_verdict(self) -> VerdictT | None:
        """Return the opaque terminal verdict for the owning application boundary."""
        return self._terminal_precondition_verdict


class CoreError(CadrumoError):
    """Base error for internal framework and core-primitive failures."""


class DecimalFormatError(CoreError):
    """Raised when :func:`core.decimal._format.format_decimal` receives an invalid argument.

    Replaces the bare :class:`TypeError` previously raised when ``value``
    is ``None`` but ``none_value`` was not provided.
    """


class RedactionError(CoreError):
    """Raised when a redaction helper receives an argument of the wrong type.

    Replaces bare :class:`TypeError` previously raised by
    :func:`core.redaction.redact` and
    :func:`core.redaction.redact_for_cli_output` when passed a
    non-``str`` argument.
    """


class CoreValidationError(CoreError, ValueError):
    """Raised when core primitives or configuration violate invariants.

    Inherits from ValueError to maintain compatibility with Pydantic
    validators.
    """


class ProfileAnswerTypeError(CoreValidationError):
    """Raised when a typed profile-answers field coercion receives an unexpected type.

    Lives in :mod:`core.errors` so :class:`core.setup_answers.SetupAnswers`
    can raise a typed error without importing application-layer wizard modules.
    Application-layer wizard code raises the narrower
    :class:`application.wizard._errors.WizardAnswerTypeError`, which
    inherits from this class, so callers catching either type continue to work.
    """


class CadrumoObservabilityError(CadrumoError):
    """Base class for observability-layer errors.

    Lives in :mod:`core.errors` (rather than the leaf
    :mod:`core.observability` subpackage) so other subpackages can catch it
    without importing observability internals. Concrete subclasses are
    declared in :mod:`core.observability._errors`.
    """


class SiteHealthError(CadrumoError):
    """Raised when AEAT site-health detection classifies a non-OK state.

    Carries a :class:`SiteHealthStatusLike` payload describing the
    detected state (mantenimiento, WAF challenge, rate limit,
    unreachable, unknown error) together with the evidence used to
    classify it. The workflow engine catches this error in a typed arm
    that precedes the generic exception handler so a planned
    mantenimiento never collapses into ``UNHANDLED_EXCEPTION``.

    The error lives in :mod:`core.errors` (and not in either leaf
    subpackage) to break the circular import between
    :mod:`adapters.outbound.aeat.browser` (which raises it) and
    :mod:`application.workflow` (which consumes it). The payload is
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


class ActiveProfilePointerError(CoreError):
    """Raised when the active-profile pointer is present but invalid.

    A missing pointer is a clean cold-start state. A present pointer that
    cannot be parsed, decoded, read, or validated is storage metadata
    corruption and does not resolve to a root fallback database route.
    """

    def __init__(self, *, path: object) -> None:
        """Construct the active-profile pointer integrity error.

        Args:
            path: Pointer file path that failed to load.
        """
        super().__init__(
            translated_message="errors.integrity.integrity_active_profile_pointer",
            context={
                "path": str(path),
                "pointer_corrupt": True,
                "root_fallback_refused": True,
            },
        )


class NoActiveProfileError(CadrumoError):
    """Raised when an operation requires an active profile bucket and none is selected.

    Bucket-scoped repositories (transaction catalogue, manual ledger,
    bucket-local aggregation) and the operator-initiated auth/sede flows refuse
    to operate without an active profile. The active-bucket precedence chain is
    a core concern (env var > pointer file), so the refusal that gates it lives
    in the core error taxonomy and is raised by
    :func:`core.require_active_bucket_id`. Callers that surface this to the
    operator map it to the standard ``cli.common.errors.no_active_profile`` message.
    """


from ._not_found import CoreNotFoundError
from ._registry import (
    ERROR_REGISTRY,
    ErrorCategory,
    ErrorCode,
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


def __getattr__(name: str) -> object:
    """Complete the error-envelope action type on first public access."""
    if name == "ErrorEnvelope":
        from ..json_contract import ResolvedPreconditionAction
        from ._registry import ErrorEnvelope

        ErrorEnvelope.model_rebuild(
            _types_namespace={"ResolvedPreconditionAction": ResolvedPreconditionAction},
        )
        globals()[name] = ErrorEnvelope
        return ErrorEnvelope
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ERROR_REGISTRY",
    "ActiveProfilePointerError",
    "BaseSeverity",
    "CadrumoError",
    "CadrumoObservabilityError",
    "CoreError",
    "CoreNotFoundError",
    "CoreValidationError",
    "DecimalFormatError",
    "ErrorCategory",
    "ErrorCode",
    "ErrorEnvelope",
    "NoActiveProfileError",
    "ProfileAnswerTypeError",
    "RedactionError",
    "SiteHealthError",
    "SiteHealthEvidenceLike",
    "SiteHealthStatusLike",
    "TerminalPreconditionErrorMixin",
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
