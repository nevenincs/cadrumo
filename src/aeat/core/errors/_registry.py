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
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict

_SECRET_FIELD_PATTERN = re.compile(
    r"(credential|token|secret|pkcs12|passphrase|cert_password|cookie|bearer)",
    re.IGNORECASE,
)


class ErrorCategory(StrEnum):
    """Closed catalogue of stable CLI error categories."""

    ERROR = "ERROR"
    REFUSED = "REFUSED"
    AUTH = "AUTH"
    INTEGRITY = "INTEGRITY"
    FAIL = "FAIL"
    INTERNAL = "INTERNAL"
    LOCKED = "LOCKED"


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
    """Machine-readable error payload emitted on stderr."""

    model_config = ConfigDict(
        frozen=True,
        strict=True,
        validate_assignment=True,
        extra="forbid",
    )

    schema_version: str = "1"
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


def register(code: ErrorCode) -> ErrorCode:
    """Register ``code`` in the global catalogue.

    Args:
        code: The error-code record to add.

    Returns:
        The same ``code`` object for fluent use at declaration sites.

    Raises:
        ValueError: If a duplicate code identifier is encountered.
    """

    existing = _ERROR_REGISTRY_MUTABLE.get(code.code)
    if existing is not None and existing != code:
        raise ValueError(f"duplicate ErrorCode registration for {code.code!r}")
    _ERROR_REGISTRY_MUTABLE[code.code] = code
    return code


from aeat.core.errors.registry import _ALL_DECLARED_ERROR_CODES  # noqa: E402

_DECLARED_CODE_BY_QUALNAME: Mapping[str, ErrorCode] = MappingProxyType(
    {qualname: register(code) for qualname, code in _ALL_DECLARED_ERROR_CODES}
)
ERROR_REGISTRY: Mapping[str, ErrorCode] = MappingProxyType(_ERROR_REGISTRY_MUTABLE)


def bind_error_code(error_type: type[BaseException]) -> ErrorCode:
    """Bind a stable :class:`ErrorCode` to ``error_type``.

    Args:
        error_type: Error class being declared.

    Returns:
        The registered :class:`ErrorCode` for ``error_type``.

    Raises:
        ValueError: If ``error_type`` has no declared registry entry.
    """

    bound = _CLASS_CODE_REGISTRY.get(error_type)
    if bound is not None:
        return bound
    qualname = _qualname(error_type)
    code = _DECLARED_CODE_BY_QUALNAME.get(qualname)
    if code is None:
        raise ValueError(f"AeatError subclass {qualname} is missing a declared ErrorCode registry entry")
    _CLASS_CODE_REGISTRY[error_type] = code
    type.__setattr__(error_type, "code", code)
    return code


def get_registered_error_code(error: BaseException | type[BaseException]) -> ErrorCode:
    """Return the registered :class:`ErrorCode` for ``error``."""

    error_type = error if isinstance(error, type) else type(error)
    code = _CLASS_CODE_REGISTRY.get(error_type)
    if code is None:
        code = bind_error_code(error_type)
    return code


def resolve_output_language() -> str:
    """Resolve the configured output language, defaulting to ``es``."""

    try:
        from ..config import load_settings

        value = load_settings().aeat_output_language
        return str(value).lower().strip()
    except (ValueError, OSError, AttributeError):
        return "es"


def scrub_error_context(context: Mapping[str, object] | None) -> dict[str, str] | None:
    """Redact secret-looking keys from ``context`` and stringify the values."""

    if not context:
        return None
    scrubbed: dict[str, str] = {}
    for key, value in sorted(context.items()):
        if _SECRET_FIELD_PATTERN.search(key):
            scrubbed[key] = "<redacted>"
        else:
            scrubbed[key] = _stringify_context_value(value)
    return scrubbed or None


def build_error_envelope(
    error: BaseException,
    *,
    context: Mapping[str, object] | None = None,
    trace_id: str | None = None,
) -> ErrorEnvelope:
    """Build the deterministic JSON stderr envelope for ``error``."""

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
    prefix = code.category.value
    message = resolve_error_message(error, code)
    first_line = f"{prefix} {message}" if prefix.startswith("[") else f"{prefix}: {message}"
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
    """Serialize ``error`` to a deterministic single-line JSON document."""

    envelope = build_error_envelope(error, context=context, trace_id=trace_id)
    payload = {"error": envelope.model_dump(mode="json")}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


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
    through the i18n backend, which falls back to the key itself if no
    matching translation exists.
    """

    resolved_code = code or get_registered_error_code(error)
    from ...entrypoints.cli._i18n import tr

    translated_message = getattr(error, "translated_message", None)
    if isinstance(translated_message, str) and translated_message:
        return tr(translated_message)
    if error.args and isinstance(error.args[0], str) and error.args[0]:
        return error.args[0]
    return tr(resolved_code.message_key)


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
        if key.startswith("_") or key in {"code", "context", "translated_message", "suggestion"}:
            continue
        merged[key] = value
    if context:
        merged.update(context)
    return merged or None


def _stringify_context_value(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float, str)):
        return str(value)
    return str(value)


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
