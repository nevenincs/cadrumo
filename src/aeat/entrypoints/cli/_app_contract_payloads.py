"""Typed ``--json`` payload schema for the ``aeat app contract`` command.

The contract command emits the operator-surface capability manifest under the
stable ``contract`` envelope key. Like the root group-callback payloads, the
manifest is an application-owned DTO
(:class:`~aeat.application.operator_surface.OperatorSurfaceManifest`) whose rich
nested shape is validated and surfaced through
:class:`~aeat.entrypoints.cli._schemas.SchemaEnvelope`; the schema accepts the
DTO fields without re-modelling every nested record in the CLI layer, matching
the precedent set by the root landing/help payloads.
"""

from __future__ import annotations

from ._schemas import OutputSchema, register_schema


@register_schema("contract")
class ContractManifestResult(OutputSchema):
    """JSON envelope for ``aeat app contract`` - the capability manifest.

    This strict :class:`~aeat.entrypoints.cli._schemas.OutputSchema` subclass
    wraps the
    :class:`~aeat.application.operator_surface.OperatorSurfaceManifest` produced
    by :func:`~aeat.application.operator_surface.build_operator_surface_manifest`
    for the operator's tool catalogue. The manifest carries the immutable
    operator-surface contract (roots, command families with mutability and
    intent, the modelo lifecycle, the source-kind taxonomy) plus the registered
    command-path result-schema references. The shape is allowed to pass through
    so the application DTO is the single source of truth for the manifest
    structure.
    """

    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class var shadows ConfigDict descriptor;
    # mypy assignment check is incorrect.
    model_config = {"extra": "allow"}  # type: ignore[assignment]
