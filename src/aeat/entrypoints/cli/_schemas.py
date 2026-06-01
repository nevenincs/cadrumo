"""CLI-local JSON-contract surface.

Re-exports the strict ``--json`` contract primitives for CLI payload modules:
the :class:`OutputSchema` base for command results, the :class:`SchemaEnvelope`
wrapper, and the registry plus emit helpers. The canonical definitions live in
:mod:`aeat.core.json_contract`; this module only re-exports them.
"""

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
