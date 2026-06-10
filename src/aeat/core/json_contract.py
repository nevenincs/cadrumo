"""Shared primitives for the CLI's strict ``--json`` output contract.

Defines the strict pydantic v2 base classes (:class:`OutputSchema`,
:class:`OutputRootSchema`), the canonical envelope shape
(:class:`SchemaEnvelope`), the schema registry
(:data:`SCHEMA_REGISTRY`), and the streaming helpers
(:func:`emit_json_document`, :func:`emit_json_success`) used by every
``--json`` code path.

Living in :mod:`aeat.core` keeps domain and adapter packages free of any
dependency on :mod:`aeat.entrypoints.cli`: a wrapped command emits its
strict-validated payload through :func:`emit_json_success` without
having to know how the CLI itself wires Click options.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
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


class OutputSchemaError(AeatError):
    """Raised when the CLI output-schema registry is misconfigured.

    Triggered by :func:`register_schema` when a non-schema class is
    decorated, when a command path is registered twice with different
    schemas, or when the command path is blank.
    """


class OutputSchema(BaseModel):
    """Strict, frozen base class for every command-specific ``--json`` payload.

    Subclasses inherit ``extra="forbid"``, ``frozen=True``, ``strict=True``,
    and ``validate_assignment=True`` so accidental field drift between
    contract and implementation surfaces as a validation error rather
    than a silently-extended payload.
    """

    model_config = _STRICT_FROZEN_CONFIG


class OutputRootSchema[RootT](RootModel[RootT]):
    """Strict root/list base class for ``--json`` payloads with a non-mapping root.

    Use this for commands whose top-level JSON value is a list or scalar
    rather than an object. Carries the same strict / frozen / validate-on-
    assignment configuration as :class:`OutputSchema`.
    """

    model_config = _STRICT_ROOT_CONFIG


class SchemaEnvelope[ResultT: OutputSchema](BaseModel):
    """Stable outer envelope wrapping a successful command's payload.

    Every successful ``--json`` response is rendered through this
    envelope so consumers can rely on the same outer keys regardless of
    the inner payload shape.

    Attributes:
        schema_version: Envelope version; bumped only on
            backwards-incompatible changes.
        command: Stable command path string (e.g. ``"workflow list"``).
        result: The strict-validated command result.
        warnings: Free-form non-fatal diagnostics surfaced to the caller.
    """

    model_config = _STRICT_FROZEN_CONFIG

    schema_version: str = Field(default="1", min_length=1)
    command: str = Field(min_length=1)
    result: ResultT
    warnings: list[str] = Field(default_factory=list)


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
    characters in the rendered output.

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
    warnings: list[str] | None = None,
    indent: int | None = 2,
    sort_keys: bool = False,
    stream: IO[str] | None = None,
) -> None:
    """Wrap ``result`` in :class:`SchemaEnvelope` and emit it via :func:`emit_json_document`.

    The envelope's ``schema_version`` is pinned to ``"1"``; bumping it
    is a contract-breaking change handled by the JSON-contract test
    suite, not a casual edit.

    Args:
        command: Stable command path string (e.g. ``"workflow list"``).
        result: The strict-validated command payload to surface as
            ``envelope.result``.
        warnings: Optional non-fatal diagnostics; defaults to an empty
            list when omitted.
        indent: Indent width forwarded to :func:`emit_json_document`.
        sort_keys: Sort-keys flag forwarded to :func:`emit_json_document`.
        stream: Target text stream; defaults to :data:`sys.stdout`.
    """
    envelope_payload = redact_structured_for_cli_output(
        {
            "schema_version": "1",
            "command": command,
            "result": _jsonable_payload(result),
            "warnings": [] if warnings is None else list(warnings),
        }
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
    existing path raises :class:`OutputSchemaError`.

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
                f"registered schema for {normalized_path!r} must be an OutputSchema or OutputRootSchema subclass"
            ) from error
        if not is_output_schema:
            raise OutputSchemaError(
                f"registered schema for {normalized_path!r} must inherit from OutputSchema or OutputRootSchema"
            )
        existing = SCHEMA_REGISTRY.get(normalized_path)
        if existing is not None and existing is not schema:
            raise OutputSchemaError(
                f"duplicate schema registration for {normalized_path!r}: {existing.__module__}.{existing.__name__}"
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
    "SCHEMA_REGISTRY",
    "OutputRootSchema",
    "OutputSchema",
    "OutputSchemaError",
    "SchemaEnvelope",
    "emit_json_document",
    "emit_json_success",
    "register_schema",
]
