"""CLI-local JSON-contract surface.

Re-exports the strict ``--json`` contract primitives for CLI payload modules:
the :class:`OutputSchema` base for command results, the :class:`SchemaEnvelope`
wrapper, the :class:`Notice` channel, and the registry plus emit helpers. The
canonical definitions live in :mod:`aeat.core.json_contract`; this module only
re-exports them so CLI payload modules have a local import surface.
"""

from __future__ import annotations

from ...core.json_contract import (
    ENVELOPE_SCHEMA_VERSION,
    SCHEMA_REGISTRY,
    EnvelopeStatus,
    Notice,
    NoticeSeverity,
    OutputRootSchema,
    OutputSchema,
    OutputSchemaError,
    SchemaEnvelope,
    derive_status,
    emit_json_document,
    emit_json_success,
    register_schema,
)

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
