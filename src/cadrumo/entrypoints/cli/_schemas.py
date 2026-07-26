"""CLI-local import surface for the shared ``--json`` contract.

Re-exports the strict :class:`OutputSchema` and :class:`OutputRootSchema` bases,
the :class:`SchemaEnvelope` wrapper, the typed :class:`Notice` channel, and the
:data:`SCHEMA_REGISTRY` / :func:`register_schema` registry API used by CLI
payload modules. The canonical definitions live in the core JSON contract; this
module exists so entrypoint payload modules can depend on a local CLI surface
while still registering against the core contract inspected by the JSON-schema
conformance gate.

Emission still flows through
:func:`_emit_envelope`, which delegates JSON mode to
:func:`~cadrumo.application.operator_output.emit_operator_json_success` and
keeps text mode on the normal renderer. ``emit_json_success`` itself is
deliberately NOT re-exported here: it is the low-level primitive behind that
funnel, and re-exporting it would hand every payload module a way to bypass
the sandbox-notice guarantee while looking like it was using the sanctioned
CLI facade (see ``test_no_bare_emit_json_success_call``). Do not add schema
conversion or command-specific business behavior here; this file is a
re-export boundary only.
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
    "register_schema",
]
