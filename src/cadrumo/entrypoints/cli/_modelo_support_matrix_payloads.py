"""JSON payload schemas for ``aeat app modelo support-matrix``.

Projects :class:`~domain.calculations.registry.ModeloEntry` (and its
nested rename / portal-compatibility records) onto the CLI's strict
:class:`~core.json_contract.OutputSchema` contract. Every field mirrors the
domain report unchanged; this module only pins the JSON transport shape.

See Also:
    :class:`~domain.calculations.registry.ModeloSupportMatrixReport`
        Domain query-service envelope this payload serializes.
    :func:`~application.modelo.registry_discovery.registry_support_matrix`
        Application query the CLI command calls to obtain the report.
    :func:`~entrypoints.cli._modelo_discovery_cli._support_matrix_entry_payload`
        Transport mapper from a domain row to this module's payload schema.
"""

from __future__ import annotations

from cadrumo.domain.calculations.registry.ids import RevisionId

from ...core.json_contract import OutputSchema


class ModeloRenamePayload(OutputSchema):
    """One declared per-ejercicio casilla continuity evolution."""

    continuidad_id: str
    from_revision: str
    to_revision: str
    evolution_kind: str


class ModeloPortalCompatibilityRefPayload(OutputSchema):
    """One declared AEAT-portal cross-reference."""

    id: str
    surface: str
    evidence_tier: str


class ModeloSupportMatrixEntryPayload(OutputSchema):
    """One modelo's support-matrix row."""

    modelo_id: str
    title: str
    calculation_class: str
    revision_count: int
    latest_revision_id: RevisionId
    latest_revision_valid_from: str
    supported_revision_ids: list[str]
    calc_grade: bool
    has_completeness_manifest: bool
    has_fixed_width_export: bool
    has_xml_dictionary_export: bool
    has_extractor: bool
    extraction_profile_count: int
    renames: list[ModeloRenamePayload]
    portal_compatibility_refs: list[ModeloPortalCompatibilityRefPayload]


class ModeloSupportMatrixResult(OutputSchema):
    """Registry-wide per-modelo support/capability matrix result."""

    operation: str = "modelo.support_matrix"
    modelo_count: int
    entries: list[ModeloSupportMatrixEntryPayload]


__all__ = [
    "ModeloPortalCompatibilityRefPayload",
    "ModeloRenamePayload",
    "ModeloSupportMatrixEntryPayload",
    "ModeloSupportMatrixResult",
]
