"""Structured error-code registry and CLI rendering helpers.

Centralises AEAT's stable CLI error taxonomy. Every
:class:`aeat.core.errors.AeatError` subclass binds to a predeclared
:class:`ErrorCode` row through :func:`bind_error_code`, so the public
contract stays explicit, reviewable, and grep-stable. Rendering helpers
:func:`render_error_text` and :func:`render_error_json` produce the
human-readable and machine-readable stderr payloads that downstream tools
consume; :func:`build_error_envelope` constructs the underlying
:class:`ErrorEnvelope`.

Secret-looking context keys (matching :data:`_SECRET_FIELD_PATTERN`) are
redacted before they ever reach stderr — see :func:`scrub_error_context`.
Non-secret context values are also passed through
:func:`aeat.core.redaction.redact_for_log` so NIF, URL, and bearer-token
shapes share the same rule vocabulary as logs and observability.
"""

from __future__ import annotations

import json
import logging as _logging_stdlib
import re
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from enum import Enum, StrEnum
from pathlib import PurePath
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict

from ..redaction import redact_for_log

# aeat.core.logging.get_logger triggers configure_logging() → config → aeat.core.errors,
# creating a circular import at module load. Use the stdlib getter here; the root
# SecretScrubbingFilter installed by configure_logging() propagates to this logger.
logger = _logging_stdlib.getLogger(__name__)

_SECRET_FIELD_PATTERN = re.compile(
    r"(credential|token|secret|pkcs12|passphrase|cert_password|cookie|bearer)",
    re.IGNORECASE,
)

# Context keys that are internal implementation detail and must not be
# surfaced in user-facing error output (text mode or JSON envelope).
# They remain accessible on the exception's `.context` attribute for
# internal diagnostics and tests.
#
# `flow_id` and `missing` are wizard internals: the wizard flow's
# identifier and the raw tuple of question ids. The operator-facing
# refusal names the missing flags inside its own message body
# (`missing_flags`, also internal once interpolated) instead of leaking
# a raw `('tax-id', 'activity')` tuple as a stray context line.
_INTERNAL_CONTEXT_KEYS: frozenset[str] = frozenset({"prompt_key", "question_id", "flow_id", "missing", "missing_flags"})


class ErrorCategory(StrEnum):
    """Closed catalogue of stable CLI error categories."""

    ERROR = "ERROR"
    REFUSED = "REFUSED"
    AUTH = "AUTH"
    INTEGRITY = "INTEGRITY"
    FAIL = "FAIL"
    INTERNAL = "INTERNAL"
    LOCKED = "LOCKED"


_TEXT_PREFIX: dict[ErrorCategory, str] = {
    ErrorCategory.ERROR: "Error.",
    ErrorCategory.REFUSED: "Refused.",
    ErrorCategory.AUTH: "Auth.",
    ErrorCategory.INTEGRITY: "Integrity.",
    ErrorCategory.FAIL: "Failed.",
    ErrorCategory.INTERNAL: "Internal.",
    ErrorCategory.LOCKED: "Locked.",
}


def _category_text_prefix(category: ErrorCategory) -> str:
    """Return the sentence-case stderr prefix for ``category``."""
    return _TEXT_PREFIX[category]


class ErrorCode(BaseModel):
    """Stable metadata attached to an :class:`aeat.core.errors.AeatError` type."""

    model_config = ConfigDict(
        frozen=True,
        strict=True,
        validate_assignment=True,
        extra="forbid",
    )

    code: str
    category: ErrorCategory
    message_key: str
    default_suggestion: str | None
    retryable: bool
    runbook_id: str | None


class ErrorEnvelope(BaseModel):
    """Machine-readable error body nested under the shared envelope spine.

    Rendered as the ``error`` member of the stderr error document. The
    document-level spine (``schema_version``, ``command``, ``status``,
    ``notices``) is added by :func:`render_error_json` so the error
    document and the success :class:`~aeat.core.json_contract.SchemaEnvelope`
    share one outer shape.
    """

    model_config = ConfigDict(
        frozen=True,
        strict=True,
        validate_assignment=True,
        extra="forbid",
    )

    code: str
    category: str
    message: str
    suggestion: str | None
    retryable: bool
    runbook_id: str | None
    context: dict[str, str] | None
    trace_id: str | None


_ERROR_REGISTRY_MUTABLE: dict[str, ErrorCode] = {}
_CLASS_CODE_REGISTRY: dict[type[BaseException], ErrorCode] = {}

# Collects AeatError subclasses whose bind_error_code call arrived before
# _DECLARED_CODE_BY_QUALNAME was fully populated (i.e. during the circular-
# import window while this module is still initialising).  get_registered_
# error_code drains this set on every call so deferred classes are bound
# at first runtime use rather than at class-creation time.
_DEFERRED_BIND: set[type[BaseException]] = set()


def register(code: ErrorCode) -> ErrorCode:
    """Register ``code`` in the global catalogue.

    Args:
        code: The :class:`ErrorCode` record to add.

    Returns:
        The same :class:`ErrorCode` object for fluent use at declaration
        sites.

    Raises:
        ValueError: If a duplicate code identifier is encountered.
    """
    existing = _ERROR_REGISTRY_MUTABLE.get(code.code)
    if existing is not None and existing != code:
        raise ValueError(f"duplicate ErrorCode registration for {code.code!r}")
    _ERROR_REGISTRY_MUTABLE[code.code] = code
    return code


from .registry import _ALL_DECLARED_ERROR_CODES

_DECLARED_CODE_BY_QUALNAME: Mapping[str, ErrorCode] = MappingProxyType(
    {qualname: register(code) for qualname, code in _ALL_DECLARED_ERROR_CODES}
)
ERROR_REGISTRY: Mapping[str, ErrorCode] = MappingProxyType(_ERROR_REGISTRY_MUTABLE)


def _flush_deferred_binds() -> None:
    """Attempt to bind any classes whose registration was deferred.

    Called at the start of get_registered_error_code so that classes
    defined during the circular-import window (before
    _DECLARED_CODE_BY_QUALNAME was ready) are bound on first runtime use.
    """
    if not _DEFERRED_BIND:
        return
    still_pending: set[type[BaseException]] = set()
    for error_type in list(_DEFERRED_BIND):
        qualname = _qualname(error_type)
        # _DECLARED_CODE_BY_QUALNAME is guaranteed populated by the time
        # any runtime call reaches here; failures here are genuine gaps.
        code = _DECLARED_CODE_BY_QUALNAME.get(qualname)
        if code is not None:
            _CLASS_CODE_REGISTRY[error_type] = code
            type.__setattr__(error_type, "code", code)
        else:
            still_pending.add(error_type)
    _DEFERRED_BIND.clear()
    _DEFERRED_BIND.update(still_pending)


def bind_error_code(error_type: type[BaseException]) -> ErrorCode | None:
    """Bind a stable :class:`ErrorCode` to ``error_type``.

    Called from ``AeatError.__init_subclass__`` at class-creation
    time.  If the global :data:`_DECLARED_CODE_BY_QUALNAME` mapping is
    not yet available (the module is still initialising due to a circular
    import) the class is added to :data:`_DEFERRED_BIND` and bound
    lazily on first use via :func:`get_registered_error_code`.

    Args:
        error_type: Error class being declared.

    Returns:
        The registered :class:`ErrorCode` for ``error_type``.

    Raises:
        ValueError: When the mapping is available but contains no entry
            for this class.
    """
    bound = _CLASS_CODE_REGISTRY.get(error_type)
    if bound is not None:
        return bound
    # _DECLARED_CODE_BY_QUALNAME is assigned at module level after the
    # registry submodule import on the line above.  During the circular-
    # import window (when another module triggers AeatError subclass
    # creation while _registry.py is still executing) this name does not
    # yet exist in the module globals.  Defer rather than crash.
    declared = globals().get("_DECLARED_CODE_BY_QUALNAME")
    if declared is None:
        _DEFERRED_BIND.add(error_type)
        # _DECLARED_CODE_BY_QUALNAME is absent during the circular-import window;
        # get_registered_error_code drains _DEFERRED_BIND after loading.
        return None
    qualname = _qualname(error_type)
    code = declared.get(qualname)
    if code is None:
        raise ValueError(
            f"AeatError subclass {qualname} is missing a declared ErrorCode "
            f"registry entry. If this class was just added, declare it in the "
            f"error-code registry alongside the class. If you encountered this "
            f"during a test run, the class may have been added by a peer agent "
            f"mid-flight: run `git status` and rerun once peer state settles."
        )
    _CLASS_CODE_REGISTRY[error_type] = code
    type.__setattr__(error_type, "code", code)
    return code


def get_registered_error_code(error: BaseException | type[BaseException]) -> ErrorCode:
    """Return the registered :class:`ErrorCode` for ``error``.

    Drains any deferred binds accumulated during the circular-import
    window before attempting the lookup, so classes defined before
    ``_DECLARED_CODE_BY_QUALNAME`` was populated are bound here on first
    runtime use.
    """
    _flush_deferred_binds()
    error_type = error if isinstance(error, type) else type(error)
    code = _CLASS_CODE_REGISTRY.get(error_type)
    if code is None:
        resolved = bind_error_code(error_type)
        # bind_error_code returns None only during the circular-import window
        # (when _DECLARED_CODE_BY_QUALNAME is absent).  Any runtime call to
        # get_registered_error_code arrives after the module has finished
        # loading so the deferred set has been drained by _flush_deferred_binds
        # above; None here would mean the class has no declared ErrorCode entry.
        if resolved is None:
            raise ValueError(
                f"AeatError subclass {_qualname(error_type)} has no registered ErrorCode "
                f"even after deferred-bind drain; ensure it is declared in the error-code registry."
            )
        code = resolved
    return code


def resolve_output_language() -> str:
    """Resolve the configured output language, defaulting to ``es``."""
    try:
        from ..i18n import output_language

        return output_language()
    except Exception as exc:
        logger.debug(
            "resolve_output_language: i18n resolution failed; falling back to 'es' (%s)",
            exc,
            exc_info=True,
        )
        return "es"


def scrub_error_context(context: Mapping[str, object] | None) -> dict[str, str] | None:
    """Redact secret-looking keys and strip internal keys from ``context``.

    Keys matching :data:`_SECRET_FIELD_PATTERN` are replaced with
    ``"<redacted>"``. Keys in :data:`_INTERNAL_CONTEXT_KEYS` are
    dropped entirely — they are implementation detail (e.g. widget
    prompt identifiers) and must not appear in operator-facing output.
    """
    if not context:
        return None
    scrubbed: dict[str, str] = {}
    for key, value in sorted(context.items()):
        if key in _INTERNAL_CONTEXT_KEYS:
            continue
        if _SECRET_FIELD_PATTERN.search(key):
            scrubbed[key] = "<redacted>"
        else:
            scrubbed[key] = redact_for_log(_stringify_context_value(value))
    return scrubbed or None


def build_error_envelope(
    error: BaseException,
    *,
    context: Mapping[str, object] | None = None,
    trace_id: str | None = None,
) -> ErrorEnvelope:
    """Build the deterministic JSON stderr envelope for ``error``.

    Returns:
        A frozen :class:`ErrorEnvelope` suitable for serialisation to
        the machine-readable stderr payload.
    """
    code = get_registered_error_code(error)
    merged_context = _merge_error_context(error, context)
    return ErrorEnvelope(
        code=code.code,
        category=code.category.value,
        message=resolve_error_message(error, code),
        suggestion=get_error_suggestion(error, code),
        retryable=code.retryable,
        runbook_id=code.runbook_id,
        context=scrub_error_context(merged_context),
        trace_id=trace_id,
    )


def render_error_text(
    error: BaseException,
    *,
    context: Mapping[str, object] | None = None,
) -> str:
    """Render the human-readable stderr payload for ``error``."""
    code = get_registered_error_code(error)
    prefix = _category_text_prefix(code.category)
    message = resolve_error_message(error, code)
    first_line = f"{prefix} {message}"
    suggestion = get_error_suggestion(error, code)
    lines = [first_line]
    if suggestion is not None:
        lines.append(f"  -> Run `{suggestion}`")
    scrubbed_context = scrub_error_context(_merge_error_context(error, context))
    if scrubbed_context:
        for key, value in scrubbed_context.items():
            lines.append(f"  {key}: {value}")
    return "\n".join(lines) + "\n"


def render_error_json(
    error: BaseException,
    *,
    context: Mapping[str, object] | None = None,
    trace_id: str | None = None,
) -> str:
    """Serialize ``error`` to a deterministic single-line JSON document.

    The document carries the shared envelope spine (``schema_version``,
    ``command``, ``status``, ``notices``) so it is shape-compatible with
    the success :class:`~aeat.core.json_contract.SchemaEnvelope`. The
    error detail is nested under ``error``. ``command`` is ``None``: the
    CLI error boundary terminates before the dotted command path is
    resolvable, so the field is present-but-null for spine uniformity.
    The :data:`~aeat.core.json_contract.ENVELOPE_SCHEMA_VERSION` import is
    function-local to avoid the ``json_contract`` <-> ``errors`` import
    cycle (``json_contract`` imports :class:`AeatError`).
    """
    from ..json_contract import ENVELOPE_SCHEMA_VERSION, EnvelopeStatus

    envelope = build_error_envelope(error, context=context, trace_id=trace_id)
    document = {
        "schema_version": ENVELOPE_SCHEMA_VERSION,
        "command": None,
        "status": EnvelopeStatus.ERROR.value,
        "error": envelope.model_dump(mode="json"),
        "notices": [],
    }
    return json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def get_error_exit_code(category: ErrorCategory) -> int:
    """Return the canonical process exit code for ``category``."""
    return {
        ErrorCategory.ERROR: 1,
        ErrorCategory.REFUSED: 2,
        ErrorCategory.AUTH: 3,
        ErrorCategory.INTEGRITY: 4,
        ErrorCategory.FAIL: 5,
        ErrorCategory.INTERNAL: 6,
        ErrorCategory.LOCKED: 7,
    }[category]


def resolve_error_message(error: BaseException, code: ErrorCode | None = None) -> str:
    """Resolve the user-facing message for ``error``.

    ``translated_message`` is a translation key (e.g.
    ``"profile.errors.not_configured"``) by convention; it is rendered
    through the i18n backend, which falls back to the key itself when
    no matching translation exists.
    """
    resolved_code = code or get_registered_error_code(error)
    from ..i18n import tr

    interpolation = _coerce_interpolation_kwargs(getattr(error, "context", None))
    translated_message = getattr(error, "translated_message", None)
    if isinstance(translated_message, str) and translated_message:
        return tr(translated_message, **interpolation)
    if error.args and isinstance(error.args[0], str) and error.args[0]:
        return error.args[0]
    return tr(resolved_code.message_key, **interpolation)


def _coerce_interpolation_kwargs(
    context: Mapping[str, object] | None,
) -> dict[str, object]:
    """Reduce a structured error context to safe kwargs for `tr(...)`.

    Preserves keys that are valid Python identifiers; drops anything
    else so a free-form context entry can never break the
    interpolation contract. Values are passed through unchanged so
    `{value}` placeholders see the same Decimal / int / str the
    error site recorded.
    """
    if context is None:
        return {}
    safe: dict[str, object] = {}
    for key, value in context.items():
        if isinstance(key, str) and key.isidentifier():
            safe[key] = value
    return safe


def get_error_suggestion(error: BaseException, code: ErrorCode | None = None) -> str | None:
    """Resolve the copy-paste recovery command for ``error``."""
    resolved_code = code or get_registered_error_code(error)
    suggestion = getattr(error, "suggestion", None)
    if isinstance(suggestion, str) and suggestion:
        return suggestion
    return resolved_code.default_suggestion


def _qualname(error_type: type[BaseException]) -> str:
    return f"{error_type.__module__}.{error_type.__name__}"


def _merge_error_context(
    error: BaseException,
    context: Mapping[str, object] | None,
) -> dict[str, object] | None:
    merged: dict[str, object] = {}
    error_context = getattr(error, "context", None)
    if isinstance(error_context, Mapping):
        merged.update(error_context)
    for key, value in vars(error).items():
        if key.startswith("_") or key in {"code", "context", "translated_message", "suggestion", "original_exception"}:
            continue
        merged[key] = value
    if context:
        merged.update(context)
    return merged or None


def _stringify_context_value(value: object) -> str:
    """Render one error-context value as an operator-safe string.

    This is the single defensive funnel for the CLI error boundary. An
    :class:`aeat.core.errors.AeatError` subclass can — accidentally or
    by design — carry a non-primitive object in its ``context`` mapping
    or as a public instance attribute (which
    :func:`_merge_error_context` folds into the context via
    ``vars(error)``). A bare ``str(value)`` on such an object emits a
    raw Python repr — ``datetime.datetime(...)`` constructor calls,
    ``<Enum.X: 'X'>`` reprs, nested pydantic/tuple structures — straight
    at a non-technical operator. That is an error-boundary
    serialization leak.

    Only primitives, the time types (rendered ISO-8601),
    :class:`enum.Enum` (rendered as ``.value``), and flat collections of
    those are stringified verbatim. Any other object is replaced with a
    stable ``<type-name>`` placeholder so the operator never sees a raw
    object dump regardless of which error class produced the context.
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float, str)):
        return str(value)
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, PurePath):
        return str(value)
    if isinstance(value, (list, tuple, frozenset, set)):
        return ", ".join(_stringify_context_value(item) for item in value)
    if isinstance(value, Mapping):
        return ", ".join(
            f"{_stringify_context_value(key)}={_stringify_context_value(item)}" for key, item in value.items()
        )
    return f"<{type(value).__name__}>"


__all__ = [
    "ERROR_REGISTRY",
    "ErrorCategory",
    "ErrorCode",
    "ErrorEnvelope",
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
