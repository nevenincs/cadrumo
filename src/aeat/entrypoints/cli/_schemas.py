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

OutputRootSchema.__module__ = __name__
OutputSchema.__module__ = __name__
OutputSchemaError.__module__ = __name__
SchemaEnvelope.__module__ = __name__
emit_json_document.__module__ = __name__
emit_json_success.__module__ = __name__
register_schema.__module__ = __name__

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
