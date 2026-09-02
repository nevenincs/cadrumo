"""Structured error-code registry and CLI rendering helpers.

Centralises Cadrumo's stable CLI error taxonomy. Every
:class:`core.errors.CadrumoError` subclass binds to a predeclared
:class:`ErrorCode` row through :func:`bind_error_code`, so the public
contract stays explicit, reviewable, and grep-stable. Rendering helpers
:func:`render_error_text` and :func:`render_error_json` produce the
human-readable and machine-readable stderr payloads that downstream tools
consume; :func:`build_error_envelope` constructs the underlying
:class:`ErrorEnvelope`.

Secret-looking context keys (matching :data:`_SECRET_FIELD_PATTERN`) are
redacted before they ever reach stderr — see :func:`scrub_error_context`.
Non-secret context values are also passed through
:func:`core.redaction.redact_for_log` so NIF, URL, and bearer-token
shapes share the same rule vocabulary as logs and observability.
"""

from __future__ import annotations

import json
import logging as _logging_stdlib
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from enum import Enum, StrEnum
from pathlib import PurePath
from types import MappingProxyType
from typing import TYPE_CHECKING, cast

from pydantic import BaseModel, ConfigDict

from ..redaction.rules import redact_for_log

if TYPE_CHECKING:
    from ..json_contract import Notice, ResolvedPreconditionAction

# cadrumo.core.logging.get_logger triggers configure_logging() → config → cadrumo.core.errors,
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


def _category_text_prefix(category: ErrorCategory) -> str:
    """Return the sentence-case stderr prefix for ``category``."""
    from ..i18n import tr

    return tr(f"errors.prefix.{category.value.lower()}")


class ErrorCode(BaseModel):
    """Stable metadata attached to an :class:`core.errors.CadrumoError` type."""

    model_config = ConfigDict(
        frozen=True,
        strict=True,
        validate_assignment=True,
        extra="forbid",
    )

    code: str
    category: ErrorCategory
    message_key: str
    retryable: bool
    """Whether repeating the IDENTICAL call may succeed with nothing else changed.

    True means time alone, or another party finishing, can make the same
    request work: a held lock, a network failure, a rate limit, a
    compare-and-swap conflict, a login throttle. False means the call cannot
    succeed until something else changes -- a different argument, an operator
    action, a state that only another command can create.

    This is not decoration. A caller of this CLI may be non-interactive,
    and this field is the instruction it acts on, so "retryable" on a
    permanently-failing call is an invitation to loop with no terminating
    condition. The field carried no stated meaning for a long time, and a
    refusal for a profile label already bound to a committed capsule inherited
    ``True`` from a sibling condition that genuinely was a stale-witness
    conflict; the identical restore could never have succeeded.

    "Retryable after the operator fixes something" is FALSE by this definition.
    The agent cannot distinguish it from the transient case, and telling it to
    retry is what produces the loop.
    """
    runbook_id: str | None


class ErrorEnvelope(BaseModel):
    """Machine-readable error body nested under the shared envelope spine.

    Rendered as the ``error`` member of the stderr error document. The
    document-level spine (``schema_version``, ``command``, ``status``,
    ``notices``) is added by :func:`render_error_json` so the error
    document and the success :class:`core.json_contract.SchemaEnvelope`
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
    action: ResolvedPreconditionAction | None = None
    retryable: bool
    runbook_id: str | None
    context: dict[str, str] | None
    trace_id: str | None


def complete_error_envelope_model() -> None:
    """Resolve the canonical action DTO into the envelope model.

    ``ErrorEnvelope`` names ``ResolvedPreconditionAction``, which lives in
    :mod:`cadrumo.core.json_contract`. This module cannot import that at
    definition time: the exception hierarchy binds its codes here while it is
    still being defined, so reaching for ``json_contract`` from module scope
    re-enters a half-built hierarchy.

    ``json_contract`` calls this at the bottom of its own module, once both
    halves exist. :func:`build_error_envelope` calls it too, so a caller that
    never touches ``json_contract`` still gets a complete model; it is
    idempotent and returns immediately when already complete.
    """
    if ErrorEnvelope.__pydantic_complete__:
        return
    from ..json_contract import ResolvedPreconditionAction

    ErrorEnvelope.model_rebuild(
        _types_namespace={"ResolvedPreconditionAction": ResolvedPreconditionAction},
    )


_ERROR_REGISTRY_MUTABLE: dict[str, ErrorCode] = {}
_CLASS_CODE_REGISTRY: dict[type[BaseException], ErrorCode] = {}

# Collects CadrumoError subclasses whose bind_error_code call arrived before
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
    if existing is not None:
        raise ValueError(f"duplicate ErrorCode registration for {code.code!r}")
    _ERROR_REGISTRY_MUTABLE[code.code] = code
    return code


from ..type_guards import is_object_mapping
from .registry.declared_codes import ALL_DECLARED_ERROR_CODES


def _build_declared_code_map(rows: tuple[tuple[str, ErrorCode], ...]) -> Mapping[str, ErrorCode]:
    """Register raw declarations while refusing duplicate class ownership."""
    declared: dict[str, ErrorCode] = {}
    for qualname, code in rows:
        if qualname in declared:
            raise ValueError(f"duplicate ErrorCode declaration for {qualname!r}")
        declared[qualname] = register(code)
    return MappingProxyType(declared)


_DECLARED_CODE_BY_QUALNAME: Mapping[str, ErrorCode] = _build_declared_code_map(ALL_DECLARED_ERROR_CODES)
ERROR_REGISTRY: Mapping[str, ErrorCode] = MappingProxyType(_ERROR_REGISTRY_MUTABLE)


def declared_error_codes() -> tuple[tuple[str, ErrorCode], ...]:
    """Return declared ``(qualified class name, :class:`ErrorCode`)`` registry rows."""
    return tuple(_DECLARED_CODE_BY_QUALNAME.items())


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

    Called from ``CadrumoError.__init_subclass__`` at class-creation
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
    # import window (when another module triggers CadrumoError subclass
    # creation while _registry.py is still executing) this name does not
    # yet exist in the module globals.  Defer rather than crash.
    declared: object = globals().get("_DECLARED_CODE_BY_QUALNAME")
    if declared is None:
        _DEFERRED_BIND.add(error_type)
        # _DECLARED_CODE_BY_QUALNAME is absent during the circular-import window;
        # get_registered_error_code drains _DEFERRED_BIND after loading.
        return None
    if not is_object_mapping(declared):
        raise RuntimeError("the declared error-code registry is not a mapping")
    qualname = _qualname(error_type)
    code = declared.get(qualname)
    if not isinstance(code, ErrorCode):
        raise ValueError(
            f"CadrumoError subclass {qualname} is missing a declared ErrorCode "
            f"registry entry. If this class was just added, declare it in the "
            f"error-code registry alongside the class. If you encountered this "
            f"during a test run, the class may have been added by a concurrent "
            f"process mid-flight: run `git status` and rerun once the working "
            f"tree settles.",
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
                f"CadrumoError subclass {_qualname(error_type)} has no registered ErrorCode "
                f"even after deferred-bind drain; ensure it is declared in the error-code registry.",
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
    action: ResolvedPreconditionAction | None = None,
    context: Mapping[str, object] | None = None,
    trace_id: str | None = None,
) -> ErrorEnvelope:
    """Build the deterministic JSON stderr envelope for ``error``.

    Returns:
        A frozen :class:`ErrorEnvelope` suitable for serialisation to
        the machine-readable stderr payload.
    """
    complete_error_envelope_model()
    code = get_registered_error_code(error)
    merged_context = _merge_error_context(error, context)
    return ErrorEnvelope(
        code=code.code,
        category=code.category.value,
        message=resolve_error_message(error, code),
        action=action,
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
    lines = [first_line]
    scrubbed_context = scrub_error_context(_merge_error_context(error, context))
    if scrubbed_context:
        for key, value in scrubbed_context.items():
            lines.append(f"  {_text_context_label(key)}: {_text_context_value(key, value)}")
    return "\n".join(lines) + "\n"


def _text_context_label(key: str) -> str:
    """Localize common human-facing context labels without changing JSON keys."""
    from ..i18n import tr

    return tr(f"errors.context_labels.{key}", default=key)


def _text_context_value(key: str, value: str) -> str:
    """Localize stable storage tokens in text mode without changing JSON values."""
    if key == "area":
        from ..i18n import tr

        return tr(f"cli.config.storage.values.area.{value}", default=value)
    return value


def render_error_json(
    error: BaseException,
    *,
    action: ResolvedPreconditionAction | None = None,
    context: Mapping[str, object] | None = None,
    trace_id: str | None = None,
    active_profile: str | None = None,
    command: str | None = None,
    notices: Sequence[Notice] = (),
) -> str:
    """Serialize ``error`` to a deterministic single-line JSON document.

    The document carries the shared envelope spine (``schema_version``,
    ``command``, ``active_profile``, ``status``, ``notices``) so it is
    shape-compatible with the success
    :class:`core.json_contract.SchemaEnvelope`. The error detail is nested
    under ``error``. ``command`` is the dotted identifier of the command that
    failed (byte-identical to the ``command=`` its success envelope would
    emit), resolved by the CLI boundary from the live click context and passed
    here; it is ``None`` only when no command has resolved yet — an argv parse
    failure before dispatch, or a direct render without a command. The ``core``
    layer never touches the click context, so the CLI boundary resolves the
    identifier and passes it. ``active_profile`` is the human label of the
    active taxpayer profile (the identity anchor), ``None`` for a
    non-profile-bound failure or when the CLI error boundary cannot resolve it;
    the ``core`` layer never scans profile manifests, so the CLI boundary
    resolves the label and passes it here. ``notices`` carries the same typed
    diagnostics the success envelope's ``notices`` channel does — the
    sandbox-active indicator above all, so a failure inside a discardable
    sandbox bucket is distinguishable from the same failure against the
    operator's real profile. ``core`` never resolves them for the same reason it
    never resolves ``active_profile``: it may not scan buckets. ``status`` stays
    :attr:`EnvelopeStatus.ERROR` regardless of notice severity — this document
    reports a failure, and no notice can soften that. The
    :data:`core.json_contract.ENVELOPE_SCHEMA_VERSION` import is function-local
    to avoid the ``json_contract`` <-> ``errors`` import cycle
    (``json_contract`` imports :class:`CadrumoError`).
    """
    from ..json_contract import ENVELOPE_SCHEMA_VERSION, EnvelopeStatus, jsonable_output_payload

    envelope = build_error_envelope(error, action=action, context=context, trace_id=trace_id)
    document = {
        "schema_version": ENVELOPE_SCHEMA_VERSION,
        "command": command,
        "active_profile": active_profile,
        "status": EnvelopeStatus.ERROR.value,
        "error": envelope.model_dump(mode="json"),
        "notices": [jsonable_output_payload(notice) for notice in notices],
    }
    return json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def get_error_exit_code(category: ErrorCategory) -> int:
    """Return the canonical process exit code for ``category``.

    The exit-code family is the operator's coarse outcome signal:

    * ``ERROR`` -> 1: an expected, operator-actionable failure or refusal of
      a *domain outcome*. A modelo verification that resolves not-granted —
      whether ``BLOCKED`` (a blocking-rule finding) or ``INCOMPLETE``
      (missing required casillas) — exits 1: both are expected verification
      verdicts, surfaced through ``typer.Exit(code=1)`` in the verify
      handler, never as an ``INTERNAL`` crash.
    * ``REFUSED`` -> 2, ``AUTH`` -> 3, ``INTEGRITY`` -> 4, ``FAIL`` -> 5,
      ``LOCKED`` -> 7: the remaining expected, registered refusal classes.
    * ``INTERNAL`` -> 6 is reserved exclusively for an *unexpected internal
      crash* (the ``INTERNAL_*`` registry codes:
      ``INTERNAL_CLI_UNEXPECTED_BOUNDARY``, ``INTERNAL_WORKFLOW_UNHANDLED``,
      etc.). An expected domain outcome MUST NOT map to ``INTERNAL`` — a
      not-granted verification verdict is a result the operator must act on,
      not a program defect, so it never exits 6.
    """
    return {
        ErrorCategory.ERROR: 1,
        ErrorCategory.REFUSED: 2,
        ErrorCategory.AUTH: 3,
        ErrorCategory.INTEGRITY: 4,
        ErrorCategory.FAIL: 5,
        ErrorCategory.INTERNAL: 6,
        ErrorCategory.LOCKED: 7,
    }[category]


def resolve_error_message(error: BaseException, code: ErrorCode | None = None, *, locale: str | None = None) -> str:
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
        return tr(translated_message, locale=locale, **interpolation)
    if error.args and isinstance(error.args[0], str) and error.args[0]:
        return error.args[0]
    return tr(resolved_code.message_key, locale=locale, **interpolation)


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
        if key.isidentifier():
            safe[key] = value
    return safe


def _qualname(error_type: type[BaseException]) -> str:
    return f"{error_type.__module__}.{error_type.__name__}"


def _merge_error_context(
    error: BaseException,
    context: Mapping[str, object] | None,
) -> dict[str, object] | None:
    merged: dict[str, object] = {}
    error_context = getattr(error, "context", None)
    if isinstance(error_context, Mapping):
        for key, value in cast("Mapping[object, object]", error_context).items():
            if isinstance(key, str):
                merged[key] = value
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
    :class:`core.errors.CadrumoError` subclass can — accidentally or
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
        return ", ".join(_stringify_context_value(item) for item in cast("Iterable[object]", value))
    if isinstance(value, Mapping):
        mapping = cast("Mapping[object, object]", value)
        return ", ".join(
            f"{_stringify_context_value(key)}={_stringify_context_value(item)}" for key, item in mapping.items()
        )
    return f"<{type(value).__name__}>"


__all__ = [
    "ERROR_REGISTRY",
    "ErrorCategory",
    "ErrorCode",
    "ErrorEnvelope",
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
