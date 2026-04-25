"""Schema registry primitives for Phase 1 of the ``--json`` contract.

The registry maps stable command paths (for example ``"status today"``)
to strict pydantic v2 output models. Phase 2 will bind real command
emitters to this registry once the sibling error-envelope branch lands.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel, ConfigDict, Field

from ..errors import AeatError

_STRICT_FROZEN_CONFIG = ConfigDict(
    extra="forbid",
    frozen=True,
    strict=True,
    validate_assignment=True,
)


class OutputSchemaError(AeatError):
    """Raised when the CLI output-schema registry is misconfigured."""


class OutputSchema(BaseModel):
    """Base class for every command-specific ``--json`` output payload."""

    model_config = _STRICT_FROZEN_CONFIG


class SchemaEnvelope[ResultT: OutputSchema](BaseModel):
    """Stable outer envelope for successful command output."""

    model_config = _STRICT_FROZEN_CONFIG

    schema_version: str = Field(default="1", min_length=1)
    command: str = Field(min_length=1)
    result: ResultT
    warnings: list[str] = Field(default_factory=list)


ResultT = TypeVar("ResultT", bound=OutputSchema)


SCHEMA_REGISTRY: dict[str, type[OutputSchema]] = {}


def register_schema(command_path: str) -> Callable[[type[ResultT]], type[ResultT]]:
    """Register a command-output schema under a stable command path.

    Args:
        command_path: Stable space-delimited command path, for example
            ``"status today"``.

    Returns:
        A class decorator that records the schema in
        :data:`SCHEMA_REGISTRY`.

    Raises:
        OutputSchemaError: If the path is blank, the schema does not inherit
            from :class:`OutputSchema`, or the path is already registered.
    """

    normalized_path = command_path.strip()
    if not normalized_path:
        raise OutputSchemaError("command_path must not be blank")

    def _decorator(schema: type[ResultT]) -> type[ResultT]:
        try:
            is_output_schema = issubclass(schema, OutputSchema)
        except TypeError as error:
            raise OutputSchemaError(
                f"registered schema for {normalized_path!r} must be an OutputSchema subclass"
            ) from error
        if not is_output_schema:
            raise OutputSchemaError(f"registered schema for {normalized_path!r} must inherit from OutputSchema")
        existing = SCHEMA_REGISTRY.get(normalized_path)
        if existing is not None and existing is not schema:
            raise OutputSchemaError(
                f"duplicate schema registration for {normalized_path!r}: {existing.__module__}.{existing.__name__}"
            )
        SCHEMA_REGISTRY[normalized_path] = schema
        return schema

    return _decorator


__all__ = ["SCHEMA_REGISTRY", "OutputSchema", "OutputSchemaError", "SchemaEnvelope", "register_schema"]
