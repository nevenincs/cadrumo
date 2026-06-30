"""Operator-surface manifest: the agent-facing capability catalogue.

Projects the backend-owned :class:`OperatorSurfaceContract` together with the
CLI's registered JSON command-result schema keys into a single machine-readable
:class:`OperatorSurfaceManifest`. This is the capability catalogue an LLM
operator reads to learn the two-root command tree, each command family's intent
and :class:`~aeat.application.operator_surface.OperatorMutability`, the modelo
``CALCULATE -> VERIFY -> FILE`` lifecycle, and the per-command result-schema
reference. It is also the natural source a tool-exposure server consumes for its
tool list.

The contract half is owned here in the application layer. The
``command_schemas`` half is the CLI's own ``--json`` result-schema registry, an
entrypoint-layer concern; the CLI adapter enumerates it and injects it into
:func:`build_operator_surface_manifest`, so this module never imports the CLI
schema registry and the hexagonal direction is preserved.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ._contract import get_operator_surface_contract
from ._models import OperatorSurfaceContract

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")


class CommandSchemaRef(BaseModel):
    """One registered command-path to result-schema reference.

    ``command`` is a stable :data:`~aeat.core.json_contract.SCHEMA_REGISTRY`
    key (e.g. ``"modelo.calculate"``); ``schema_name`` is the registered
    :class:`~aeat.core.json_contract.OutputSchema` subclass name an operator (or
    a tool-exposure server) resolves to read the command's result shape.
    """

    model_config = _STRICT_FROZEN

    command: str = Field(min_length=1)
    schema_name: str = Field(min_length=1)


class OperatorSurfaceManifest(BaseModel):
    """Agent-facing capability catalogue over the operator surface.

    Wraps the immutable :class:`OperatorSurfaceContract` (roots, mounted
    command families with their mutability and intent, modelo lifecycle,
    source-kind taxonomy, service owners) and the CLI's registered result-schema
    references. An LLM operator reads one manifest to discover what the CLI can
    do, which verbs mutate state, and where each command's result schema lives,
    instead of scraping ``--help``.
    """

    model_config = _STRICT_FROZEN

    manifest_version: str = "1"
    envelope_schema_version: str = Field(min_length=1)
    contract: OperatorSurfaceContract
    command_schemas: tuple[CommandSchemaRef, ...]


def build_operator_surface_manifest(
    *,
    envelope_schema_version: str,
    command_schemas: tuple[CommandSchemaRef, ...],
) -> OperatorSurfaceManifest:
    """Build the :class:`OperatorSurfaceManifest` from the cached contract.

    The contract is read from
    :func:`~aeat.application.operator_surface.get_operator_surface_contract`.
    The ``envelope_schema_version`` and ``command_schemas`` are supplied by the
    CLI adapter, which owns the JSON-contract registry; this keeps the
    application layer free of any dependency on the entrypoint package.

    Args:
        envelope_schema_version: The shared CLI envelope contract version
            (``ENVELOPE_SCHEMA_VERSION``) the manifest documents.
        command_schemas: The registered command-path to result-schema
            references, enumerated by the CLI from its schema registry.

    Returns:
        The validated :class:`OperatorSurfaceManifest`.
    """
    contract: OperatorSurfaceContract = get_operator_surface_contract()
    return OperatorSurfaceManifest(
        envelope_schema_version=envelope_schema_version,
        contract=contract,
        command_schemas=command_schemas,
    )
