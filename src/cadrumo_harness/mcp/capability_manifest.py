"""Consumer-owned capability manifest for the MCP harness.

The product exposes protocol-neutral command and schema contracts.  This module
is the adapter that packages those contracts for an external tool client; the
base application deliberately has no model for that consumer-facing document.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from cadrumo.application.operator_surface.contract import get_operator_surface_contract
from cadrumo.application.operator_surface.manifest import CommandSchemaRef
from cadrumo.application.operator_surface.models import OperatorSurfaceContract

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")


class OperatorSurfaceManifest(BaseModel):
    """Capability catalogue emitted by the MCP harness to its clients."""

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
    """Project product-owned contracts into the harness capability document."""
    return OperatorSurfaceManifest(
        envelope_schema_version=envelope_schema_version,
        contract=get_operator_surface_contract(),
        command_schemas=command_schemas,
    )


__all__ = ["OperatorSurfaceManifest", "build_operator_surface_manifest"]
