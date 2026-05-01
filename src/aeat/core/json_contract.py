"""Shared JSON-contract primitives that must not import ``aeat.entrypoints.cli``."""

from __future__ import annotations

import contextlib
import json
import sys
from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, RootModel

from .errors import AeatError

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
    """Raised when the CLI output-schema registry is misconfigured."""


class OutputSchema(BaseModel):
    """Base class for every command-specific ``--json`` output payload."""

    model_config = _STRICT_FROZEN_CONFIG


class OutputRootSchema[RootT](RootModel[RootT]):
    """Base class for strict root/list ``--json`` payloads."""

    model_config = _STRICT_ROOT_CONFIG


class SchemaEnvelope[ResultT: OutputSchema](BaseModel):
    """Stable outer envelope for successful command output."""

    model_config = _STRICT_FROZEN_CONFIG

    schema_version: str = Field(default="1", min_length=1)
    command: str = Field(min_length=1)
    result: ResultT
    warnings: list[str] = Field(default_factory=list)


type RegisteredSchema = type[OutputSchema] | type[OutputRootSchema[Any]]


SCHEMA_REGISTRY: dict[str, RegisteredSchema] = {}


@runtime_checkable
class _ReconfigurableStream(Protocol):
    """Text stream that supports runtime encoding reconfiguration."""

    def reconfigure(self, *, encoding: str, errors: str) -> None:
        """Reconfigure the underlying text stream."""


def emit_json_document(
    payload: Any,
    *,
    indent: int | None = 2,
    sort_keys: bool = False,
    stream: Any = None,
) -> None:
    """Emit one UTF-8 JSON document to stdout."""

    target = sys.stdout if stream is None else stream
    if isinstance(target, _ReconfigurableStream):
        with contextlib.suppress(Exception):
            target.reconfigure(encoding="utf-8", errors="strict")
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
    result: Any,
    *,
    warnings: list[str] | None = None,
    indent: int | None = 2,
    sort_keys: bool = False,
    stream: Any = None,
) -> None:
    """Emit one successful command result inside the shared schema envelope."""

    emit_json_document(
        {
            "schema_version": "1",
            "command": command,
            "result": _jsonable_payload(result),
            "warnings": [] if warnings is None else list(warnings),
        },
        indent=indent,
        sort_keys=sort_keys,
        stream=stream,
    )


def register_schema(command_path: str) -> Callable[[RegisteredSchema], RegisteredSchema]:
    """Register a command-output schema under a stable command path."""

    normalized_path = command_path.strip()
    if not normalized_path:
        raise OutputSchemaError("command_path must not be blank")

    def _decorator(schema: RegisteredSchema) -> RegisteredSchema:
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


def _jsonable_payload(payload: Any) -> Any:
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
