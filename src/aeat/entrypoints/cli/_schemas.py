"""CLI-local JSON-contract surface."""

from __future__ import annotations

from ...core.json_contract import (
    SCHEMA_REGISTRY,
    OutputRootSchema,
    OutputSchema,
    OutputSchemaError,
    SchemaEnvelope,
    emit_json_document,
    emit_json_success,
    register_schema,
)

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
