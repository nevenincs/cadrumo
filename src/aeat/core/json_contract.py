"""Shared primitives for the CLI's strict ``--json`` output contract.

Defines the strict pydantic v2 bases (:class:`OutputSchema`,
:class:`OutputRootSchema`), the canonical success envelope
(:class:`SchemaEnvelope`), the typed diagnostic channel
(:class:`Notice`), the schema registry (:data:`SCHEMA_REGISTRY`), and
the emit helpers (:func:`emit_json_document`, :func:`emit_json_success`)
used by every registered machine-output path.  CLI payload modules import
these primitives through :mod:`aeat.entrypoints.cli._schemas`, register
result models with :func:`register_schema`, and route JSON mode through
:func:`aeat.entrypoints.cli._common._emit_envelope`.

:func:`emit_json_success` derives :class:`EnvelopeStatus` from supplied
:class:`Notice` values via :func:`derive_status` and applies
:func:`aeat.core.redaction.redact_structured_for_cli_output` to the
entire envelope before writing stdout.  Text output remains owned by
:func:`aeat.core.output_rendering.render_command_output`, so redaction
and the ``reveal_cli_identifiers_opt_in`` switch stay consistent across
text and JSON surfaces.

Living in :mod:`aeat.core` keeps domain and adapter packages free of any
dependency on :mod:`aeat.entrypoints.cli`: a wrapped command emits its
strict-validated payload through :func:`emit_json_success` without
having to know how the CLI itself wires Click options.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Sequence
from enum import StrEnum
from typing import IO, Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, RootModel

from .errors import AeatError
from .logging import get_logger
from .redaction import redact_structured_for_cli_output

_log = get_logger(__name__)

_STRICT_FROZEN_CONFIG = ConfigDict(
    extra="forbid",
    frozen=True,
    strict=True,
    validate_assignment=True,
)
_STRICT_ROOT_CONFIG = ConfigDict(
    frozen=True,
    strict=True,
    validate_assignment=True,
)

#: Envelope contract version shared by the success :class:`SchemaEnvelope`
#: and the stderr error envelope. Both documents carry the same outer
#: spine (``schema_version``, ``command``, ``status``, ``notices``), so the
#: version is pinned once here and bumped only on a backwards-incompatible
#: change to that spine.
ENVELOPE_SCHEMA_VERSION = "2"


class EnvelopeStatus(StrEnum):
    """Outcome discriminator carried on every CLI return document.

    ``success`` and ``warning`` ride on the stdout :class:`SchemaEnvelope`
    (``warning`` when the command attached at least one warning-severity
    :class:`Notice`); ``error`` rides on the stderr error envelope. A
    machine consumer reads this single field to learn the outcome instead
    of branching on stdout-vs-stderr, and :func:`derive_status` is the
    success-envelope authority for computing it.
    """

    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class NoticeSeverity(StrEnum):
    """Severity of a single operator-facing :class:`Notice`.

    ``info`` is a non-fatal next-step hint or informational advisory;
    ``warning`` is a non-blocking advisory the operator should act on. A
    command that attaches any ``warning`` notice resolves to
    :attr:`EnvelopeStatus.WARNING` through :func:`derive_status`.
    """

    INFO = "info"
    WARNING = "warning"


class Notice(BaseModel):
    """One typed, non-blocking diagnostic on the envelope ``notices`` channel.

    The single uniform surface for operator-facing warnings, advisories,
    and next-step hints across every command. Domain diagnostics (e.g.
    ``ModeloFinding``, source-resolution advisories) are projected into
    this shape rather than re-modelled as bespoke per-command payload
    fields.  CLI helpers such as
    :func:`aeat.entrypoints.cli._common._emit_envelope` pass these values
    to :func:`emit_json_success`, while text renderers fold equivalent
    prose into their line output.

    Attributes:
        severity: ``info`` or ``warning``; drives the envelope ``status``.
        code: Stable machine-readable notice identifier (e.g.
            ``"modelo.calculate.unconsumed_iva"``).
        message: Operator-facing rendered text for the notice.
        suggestion: Optional copy-paste command or next-step action,
            mirroring the error envelope's ``suggestion`` field.
        context: Optional structured provenance for the notice (e.g. the
            source-resolution ``reason`` / ``source_kind``), mirroring the
            error envelope's ``context`` so a migrated advisory keeps its
            machine-queryable sub-fields without a bespoke payload model.
    """

    model_config = _STRICT_FROZEN_CONFIG

    severity: NoticeSeverity
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    suggestion: str | None = None
    context: dict[str, str] | None = None


def derive_status(notices: Sequence[Notice]) -> EnvelopeStatus:
    """Return :attr:`EnvelopeStatus.WARNING` if any notice is warning-severity.

    Success documents never carry :attr:`EnvelopeStatus.ERROR`; that
    status is reserved for the stderr error envelope. The returned
    :class:`EnvelopeStatus` is the stdout :class:`SchemaEnvelope` status
    used by :func:`emit_json_success`.
    """
    for notice in notices:
        if notice.severity is NoticeSeverity.WARNING:
            return EnvelopeStatus.WARNING
    return EnvelopeStatus.SUCCESS


class OutputSchemaError(AeatError):
    """Raised when the CLI output-schema registry is misconfigured.

    Triggered by :func:`register_schema` when a non-schema class is
    decorated, when a command path is registered twice with different
    schemas, or when the command path is blank.  It deliberately inherits
    :class:`aeat.core.errors.AeatError` so registry defects route through
    the shared CLI error boundary instead of bypassing structured output.
    """


class OutputSchema(BaseModel):
    """Strict, frozen base class for every command-specific ``--json`` payload.

    Subclasses inherit ``extra="forbid"``, ``frozen=True``, ``strict=True``,
    and ``validate_assignment=True`` so accidental field drift between
    contract and implementation surfaces as a validation error rather
    than a silently-extended payload.  Each concrete result model should
    be decorated with :func:`register_schema` so the CLI conformance gate
    can match command leaves against :data:`SCHEMA_REGISTRY`.
    """

    model_config = _STRICT_FROZEN_CONFIG


class OutputRootSchema[RootT](RootModel[RootT]):
    """Strict root/list base class for ``--json`` payloads with a non-mapping root.

    Use this for commands whose top-level JSON value is a list or scalar
    rather than an object. Carries the same strict / frozen / validate-on-
    assignment configuration as :class:`OutputSchema`, and participates in
    the same :func:`register_schema` registry contract.
    """

    model_config = _STRICT_ROOT_CONFIG


class SchemaEnvelope[ResultT: OutputSchema](BaseModel):
    """Stable outer envelope wrapping a successful command's payload.

    Every successful ``--json`` response is rendered through this
    envelope so consumers can rely on the same outer keys regardless of
    the inner payload shape. The outer spine (``schema_version``,
    ``command``, ``status``, ``notices``) is shared with the stderr error
    envelope so one shape describes success, warning, and error outcomes.
    :func:`emit_json_success` constructs the runtime mapping and the
    JSON-contract conformance gate specialises this generic envelope over
    every schema in :data:`SCHEMA_REGISTRY`.

    Attributes:
        schema_version: Envelope version; bumped only on
            backwards-incompatible changes to the shared spine.
        command: Stable command path string (e.g. ``"workflow list"``).
        status: Outcome discriminator (``success`` or ``warning`` here).
        result: The strict-validated command result.
        notices: Typed non-blocking diagnostics (warnings, advisories,
            next-step hints) surfaced to the caller. Replaces the former
            free-form ``warnings`` string list.
    """

    model_config = _STRICT_FROZEN_CONFIG

    schema_version: str = Field(default=ENVELOPE_SCHEMA_VERSION, min_length=1)
    command: str = Field(min_length=1)
    status: EnvelopeStatus
    result: ResultT
    notices: list[Notice] = Field(default_factory=list)


type RegisteredSchema = type[OutputSchema] | type[OutputRootSchema[Any]]


SCHEMA_REGISTRY: dict[str, RegisteredSchema] = {}
"""Process-global registry mapping command-path strings to their result schema.

Populated by the :func:`register_schema` decorator at import time.
Consumers (notably the doc generator and the JSON-contract conformance
tests) iterate over this mapping to enumerate every contract a release
exposes."""


@runtime_checkable
class _ReconfigurableStream(Protocol):
    """Structural type for text streams that support runtime reconfiguration.

    Matches :class:`io.TextIOWrapper` so :func:`emit_json_document` can
    pin stdout to UTF-8 without a hard isinstance check on the concrete
    class — useful for tests that pass in a :class:`io.StringIO`.
    """

    def reconfigure(self, *, encoding: str, errors: str) -> None:
        """Reset the stream's encoding and error-handling mode."""
        ...

    def write(self, s: str, /) -> int:
        """Write ``s`` to the stream and return the number of characters written."""
        ...

    def flush(self) -> None:
        """Flush the write buffers."""
        ...


def emit_json_document(
    payload: object,
    *,
    indent: int | None = 2,
    sort_keys: bool = False,
    stream: IO[str] | None = None,
) -> None:
    r"""Serialise ``payload`` and write a single UTF-8 JSON document followed by ``\\n``.

    When ``stream`` exposes ``_ReconfigurableStream.reconfigure``,
    the helper pins it to ``encoding="utf-8", errors="strict"`` first so
    downstream cp1252 consoles can not silently corrupt non-ASCII
    characters in the rendered output. This is the low-level writer used
    by :func:`emit_json_success`; it does not itself apply the envelope or
    redaction policy.

    Args:
        payload: Any object reachable by :func:`_jsonable_payload`
            (typically a :class:`pydantic.BaseModel`, a mapping, or a
            collection thereof).
        indent: Indent width passed to :func:`json.dumps`; ``None``
            produces a single-line document.
        sort_keys: Whether to render mapping keys in lexicographic order.
        stream: Target text stream; defaults to :data:`sys.stdout`.
    """
    target = sys.stdout if stream is None else stream
    if isinstance(target, _ReconfigurableStream):
        try:
            target.reconfigure(encoding="utf-8", errors="strict")
        except (OSError, ValueError, AttributeError) as exc:
            _log.debug(
                "json_contract: stdout reconfigure to UTF-8 failed; emitting with current encoding (%s)",
                exc,
            )
    document = json.dumps(
        _jsonable_payload(payload),
        ensure_ascii=False,
        indent=indent,
        sort_keys=sort_keys,
        default=str,
    )
    target.write(f"{document}\n")
    target.flush()


def emit_json_success(
    command: str,
    result: object,
    *,
    notices: Sequence[Notice] | None = None,
    indent: int | None = 2,
    sort_keys: bool = False,
    stream: IO[str] | None = None,
) -> None:
    """Wrap ``result`` in the success spine and emit it via :func:`emit_json_document`.

    The envelope's ``schema_version`` is pinned to
    :data:`ENVELOPE_SCHEMA_VERSION`; bumping it is a contract-breaking
    change handled by the JSON-contract test suite, not a casual edit.
    The ``status`` is derived from the supplied notices
    (:func:`derive_status`) so the JSON outcome and the shell exit code
    never disagree. The assembled envelope is redacted through
    :func:`aeat.core.redaction.redact_structured_for_cli_output` before
    :func:`emit_json_document` writes it.

    Args:
        command: Stable command path string (e.g. ``"workflow list"``).
        result: The strict-validated command payload to surface as
            ``envelope.result``.
        notices: Optional typed :class:`Notice` diagnostics (warnings,
            advisories, next-step hints); defaults to an empty list.
        indent: Indent width forwarded to :func:`emit_json_document`.
        sort_keys: Sort-keys flag forwarded to :func:`emit_json_document`.
        stream: Target text stream; defaults to :data:`sys.stdout`.
    """
    from .output_rendering import reveal_cli_identifiers_opt_in

    resolved_notices = [] if notices is None else list(notices)
    envelope_payload = redact_structured_for_cli_output(
        {
            "schema_version": ENVELOPE_SCHEMA_VERSION,
            "command": command,
            "status": derive_status(resolved_notices).value,
            "result": _jsonable_payload(result),
            "notices": [_jsonable_payload(notice) for notice in resolved_notices],
        },
        reveal_identifiers=reveal_cli_identifiers_opt_in(),
    )
    emit_json_document(
        envelope_payload,
        indent=indent,
        sort_keys=sort_keys,
        stream=stream,
    )


def register_schema[RegisteredSchemaT: OutputSchema | OutputRootSchema[Any]](
    command_path: str,
) -> Callable[[type[RegisteredSchemaT]], type[RegisteredSchemaT]]:
    """Decorator that binds a strict schema to a stable ``command_path``.

    Usage::

        @register_schema("workflow list")
        class WorkflowListResult(OutputSchema):
            ...

    The same schema may register the same path more than once
    (idempotent re-import); registering a *different* schema under an
    existing path raises :class:`OutputSchemaError`.  Registered paths are
    the authoritative command strings emitted as
    :attr:`SchemaEnvelope.command` and compared against the Typer command
    tree by the JSON-schema conformance tests.

    Args:
        command_path: Stable command-path string used both as the
            registry key and as the value emitted under
            :attr:`SchemaEnvelope.command`.

    Returns:
        The decorator, returning the schema class unchanged.

    Raises:
        OutputSchemaError: When ``command_path`` is blank, when the
            decorated class is not a strict schema subclass, or when the
            path is already bound to a different schema.
    """
    normalized_path = command_path.strip()
    if not normalized_path:
        raise OutputSchemaError("command_path must not be blank")

    def _decorator(schema: type[RegisteredSchemaT]) -> type[RegisteredSchemaT]:
        try:
            is_output_schema = issubclass(schema, (OutputSchema, OutputRootSchema))
        except TypeError as error:
            raise OutputSchemaError(
                f"registered schema for {normalized_path!r} must be an OutputSchema or OutputRootSchema subclass",
            ) from error
        if not is_output_schema:
            raise OutputSchemaError(
                f"registered schema for {normalized_path!r} must inherit from OutputSchema or OutputRootSchema",
            )
        existing = SCHEMA_REGISTRY.get(normalized_path)
        if existing is not None and existing is not schema:
            raise OutputSchemaError(
                f"duplicate schema registration for {normalized_path!r}: {existing.__module__}.{existing.__name__}",
            )
        SCHEMA_REGISTRY[normalized_path] = schema
        return schema

    return _decorator


def _jsonable_payload(payload: object) -> object:
    """Recursively coerce ``payload`` to JSON-serialisable primitives.

    :class:`pydantic.BaseModel` instances are dumped via ``model_dump``,
    mappings are walked key-wise, sequences and sets are walked
    element-wise, and every other value passes through unchanged (with
    :func:`json.dumps` falling back to ``default=str`` for anything
    unrecognised).
    """
    if isinstance(payload, BaseModel):
        return payload.model_dump(mode="json")
    if isinstance(payload, dict):
        return {key: _jsonable_payload(value) for key, value in payload.items()}
    if isinstance(payload, list | tuple | set | frozenset):
        return [_jsonable_payload(item) for item in payload]
    return payload


__all__ = [
    "ENVELOPE_SCHEMA_VERSION",
    "SCHEMA_REGISTRY",
    "EnvelopeStatus",
    "Notice",
    "NoticeSeverity",
    "OutputRootSchema",
    "OutputSchema",
    "OutputSchemaError",
    "SchemaEnvelope",
    "derive_status",
    "emit_json_document",
    "emit_json_success",
    "register_schema",
]
