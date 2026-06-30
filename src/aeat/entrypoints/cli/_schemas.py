"""CLI-local import surface for the shared ``--json`` contract.

Re-exports the strict :class:`~aeat.core.json_contract.OutputSchema` and
:class:`~aeat.core.json_contract.OutputRootSchema` bases, the
:class:`~aeat.core.json_contract.SchemaEnvelope` wrapper, the typed
:class:`~aeat.core.json_contract.Notice` channel, and the
:data:`~aeat.core.json_contract.SCHEMA_REGISTRY` /
:func:`~aeat.core.json_contract.register_schema` registry API used by CLI
payload modules. The canonical definitions live
in :mod:`~aeat.core.json_contract`; this module exists so entrypoint payload
modules can depend on a local CLI surface while still registering against
the core contract inspected by the JSON-schema conformance gate.

Emission still flows through
:func:`~aeat.entrypoints.cli._common._emit_envelope`, which delegates JSON mode
to :func:`~aeat.core.json_contract.emit_json_success` and keeps text mode on
the normal renderer. Do not add schema conversion or command-specific
business behavior here; this file is a re-export boundary only.
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
