"""Typed ``--json`` payload schema for the ``aeat app contract`` command.

The contract command emits the operator-surface capability manifest under the
stable ``contract`` envelope key. Like the root group-callback payloads, the
manifest is an application-owned DTO
(:class:`OperatorSurfaceManifest`) whose rich nested shape is validated and
surfaced through :class:`SchemaEnvelope`; the schema accepts the DTO fields
without re-modelling every nested record in the CLI layer, matching the precedent
set by the root landing/help payloads.
"""

from __future__ import annotations

from pydantic import Field

from ...application.operator_surface import CommandSchemaRef, OperatorSurfaceContract
from ._schemas import OutputSchema, register_schema


@register_schema("contract")
class ContractManifestResult(OutputSchema):
    """JSON envelope for ``aeat app contract`` - the capability manifest.

    This strict :class:`OutputSchema` subclass wraps the
    :class:`OperatorSurfaceManifest` produced by
    :func:`build_operator_surface_manifest` for the operator's tool catalogue.
    The manifest carries the immutable operator-surface contract (roots, command
    families with mutability and intent, the modelo lifecycle, the source-kind
    taxonomy) plus the registered command-path result-schema references. The
    shape is allowed to pass through so the application DTO is the single source
    of truth for the manifest structure.
    """

    manifest_version: str = "1"
    envelope_schema_version: str = Field(min_length=1)
    contract: OperatorSurfaceContract
    command_schemas: tuple[CommandSchemaRef, ...]
