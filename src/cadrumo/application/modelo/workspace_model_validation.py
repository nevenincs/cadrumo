"""Private consistency validators for the public Modelo Workspace DTOs."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .workspace_models import (
        ModeloWorkspaceBoundedFacetV1,
        ModeloWorkspaceCapabilityV1,
        ModeloWorkspaceContributorIdentityV1,
        ModeloWorkspaceMaterializationRecordV1,
        ModeloWorkspaceProjectionV1,
        ModeloWorkspaceProvenanceRecordV1,
    )


def require_unique_contributor_identities(
    value: tuple[ModeloWorkspaceContributorIdentityV1, ...],
) -> tuple[ModeloWorkspaceContributorIdentityV1, ...]:
    """Keep each pinned contributor tuple deterministic without declaring its port contract."""
    identities = tuple((contributor.owner, contributor.producer) for contributor in value)
    if not identities or len(set(identities)) != len(identities):
        raise ValueError("workspace contributors must be non-empty and unique")
    return tuple(sorted(value, key=lambda contributor: (contributor.owner, contributor.producer)))


def complete_capability_denominator(
    value: tuple[ModeloWorkspaceCapabilityV1, ...],
) -> tuple[ModeloWorkspaceCapabilityV1, ...]:
    """Keep both successful admission arms on the one closed capability inventory."""
    from .workspace_models import ModeloWorkspaceCapabilityName

    capability_set = {capability.capability for capability in value}
    if capability_set != set(ModeloWorkspaceCapabilityName) or len(value) != len(capability_set):
        raise ValueError("workspace capability rows must cover each V1 capability exactly once")
    return tuple(sorted(value, key=lambda capability: capability.capability.value))


def require_facet_baseline_coordinate[RecordT](facet: ModeloWorkspaceBoundedFacetV1[RecordT]) -> None:
    """Keep a page's baseline fields aligned with its copied root coordinates."""
    if facet.baseline.contract_version != facet.contract_version:
        raise ValueError("workspace facet baseline must retain the V1 contract version")
    if facet.baseline.selected_revision_id != facet.selected_revision_id:
        raise ValueError("workspace facet baseline must retain the selected revision")
    if facet.baseline.schema_identity != facet.schema_identity:
        raise ValueError("workspace facet baseline must retain the schema identity and fingerprint")
    if facet.baseline.contributor_epoch_digest != facet.contributor_epoch_digest:
        raise ValueError("workspace facet baseline must retain the contributor epoch digest")


def require_facet_page_state[RecordT](facet: ModeloWorkspaceBoundedFacetV1[RecordT]) -> None:
    """Keep page size and continuation state mutually consistent."""
    if len(facet.records) > facet.page_size:
        raise ValueError("workspace facet cannot contain more records than its page_size")
    if facet.has_more != (facet.next_cursor is not None):
        raise ValueError("workspace facet has_more must agree with next_cursor")


def require_facet_cursor_coordinate[RecordT](facet: ModeloWorkspaceBoundedFacetV1[RecordT]) -> None:
    """Keep a continuation cursor on the complete facet consistency coordinate."""
    if facet.next_cursor is not None and (
        facet.next_cursor.contract_version != facet.contract_version
        or facet.next_cursor.baseline != facet.baseline
        or facet.next_cursor.selected_revision_id != facet.selected_revision_id
        or facet.next_cursor.schema_identity != facet.schema_identity
        or facet.next_cursor.facet is not facet.facet
        or facet.next_cursor.contributor_epoch_digest != facet.contributor_epoch_digest
    ):
        raise ValueError("workspace cursor must retain the complete facet consistency coordinate")


def require_facet_availability_payload[RecordT](facet: ModeloWorkspaceBoundedFacetV1[RecordT]) -> None:
    """Refuse data-bearing page state for a non-available facet disposition."""
    from .workspace_models import ModeloWorkspaceCapabilityDisposition

    if facet.disposition is not ModeloWorkspaceCapabilityDisposition.AVAILABLE and (
        facet.records or facet.has_more or facet.next_cursor is not None
    ):
        raise ValueError("unavailable workspace facets cannot carry records or cursors")


def require_projection_schema_facet_name(projection: ModeloWorkspaceProjectionV1) -> None:
    """Require the schema facet to occupy the schema slot in every projection."""
    from .workspace_models import ModeloWorkspaceFacetName

    if projection.schema_facet.facet is not ModeloWorkspaceFacetName.SCHEMA:
        raise ValueError("workspace projection schema_facet must declare the schema facet")


def require_projection_baseline_coordinate(projection: ModeloWorkspaceProjectionV1) -> None:
    """Keep the projection baseline pinned to its resolved target and schema."""
    if projection.baseline.target != projection.target:
        raise ValueError("workspace baseline must pin the exact resolved target")
    if projection.baseline.selected_revision_id != projection.target.law_selected_revision_id:
        raise ValueError("workspace baseline must pin the exact law-selected revision")
    if projection.baseline.schema_identity != projection.schema_identity:
        raise ValueError("workspace baseline must pin the exact schema identity")


def require_projection_schema_facet_coordinate(projection: ModeloWorkspaceProjectionV1) -> None:
    """Keep schema-facet contract and revision coordinates at the projection root."""
    if projection.schema_facet.contract_version != projection.contract_version:
        raise ValueError("workspace schema facet must retain the V1 contract version")
    if projection.schema_facet.selected_revision_id != projection.target.law_selected_revision_id:
        raise ValueError("workspace schema facet must retain the law-selected revision")


def require_projection_schema_facet_identity(projection: ModeloWorkspaceProjectionV1) -> None:
    """Keep schema-facet identity and baseline aligned with the projection."""
    if projection.schema_facet.schema_identity != projection.schema_identity:
        raise ValueError("workspace schema facet must retain the schema identity and fingerprint")
    if projection.schema_facet.baseline != projection.baseline:
        raise ValueError("workspace schema facet must retain the projection baseline")


def require_projection_schema_facet_contributors(projection: ModeloWorkspaceProjectionV1) -> None:
    """Keep the schema facet on the projection's contributor epoch and tuple."""
    if projection.schema_facet.contributor_epoch_digest != projection.baseline.contributor_epoch_digest:
        raise ValueError("workspace schema facet must retain the contributor epoch digest")
    if projection.schema_facet.contributors != projection.contributors:
        raise ValueError("workspace schema facet must retain the contributor tuple")


def require_projection_capability_coordinates(projection: ModeloWorkspaceProjectionV1) -> None:
    """Keep every capability answer on the exact resolved target and revision."""
    for capability in projection.capabilities:
        if (
            capability.target != projection.target
            or capability.selected_revision_id != projection.target.law_selected_revision_id
        ):
            raise ValueError("workspace capabilities must retain the exact target and revision coordinate")


def require_projection_readiness_coordinate(projection: ModeloWorkspaceProjectionV1) -> None:
    """Keep optional readiness on the exact resolved target and revision coordinate."""
    if projection.readiness is not None and (
        projection.readiness.modelo != projection.target.modelo
        or projection.readiness.revision_id != projection.target.law_selected_revision_id
        or projection.readiness.filing_year != projection.target.filing_year
        or projection.readiness.period != projection.target.period
    ):
        raise ValueError("workspace readiness must retain the exact target and revision coordinate")


def require_static_projection_scope(projection: ModeloWorkspaceProjectionV1) -> None:
    """Keep static inspection free of materialized facets and review output."""
    from .workspace_models import ModeloWorkspaceCapabilityDisposition

    if projection.materialization_facet is not None or projection.provenance_facet is not None:
        raise ValueError("static inspection cannot carry materialization or provenance facets")
    if projection.work_review.disposition is ModeloWorkspaceCapabilityDisposition.AVAILABLE:
        raise ValueError("static inspection cannot carry a materialized work review")


def require_graded_projection_facets(
    projection: ModeloWorkspaceProjectionV1,
) -> tuple[
    ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceMaterializationRecordV1],
    ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceProvenanceRecordV1],
]:
    """Require both data-bearing facets before checking their canonical coordinates."""
    materialization_facet = projection.materialization_facet
    provenance_facet = projection.provenance_facet
    if materialization_facet is None or provenance_facet is None:
        raise ValueError("graded snapshot requires materialization and provenance facets")
    return materialization_facet, provenance_facet


def require_graded_projection_facet_names(
    materialization_facet: ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceMaterializationRecordV1],
    provenance_facet: ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceProvenanceRecordV1],
) -> None:
    """Keep graded data-bearing facets in their canonical materialization/provenance slots."""
    from .workspace_models import ModeloWorkspaceFacetName

    expected = (
        (materialization_facet, ModeloWorkspaceFacetName.MATERIALIZATION),
        (provenance_facet, ModeloWorkspaceFacetName.PROVENANCE),
    )
    if any(facet.facet is not expected_name for facet, expected_name in expected):
        raise ValueError("graded snapshot facets must retain their canonical names")


def require_graded_projection_facet_coordinates(
    projection: ModeloWorkspaceProjectionV1,
    materialization_facet: ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceMaterializationRecordV1],
    provenance_facet: ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceProvenanceRecordV1],
) -> None:
    """Keep each graded facet on the projection's complete root consistency coordinate."""
    for facet in (materialization_facet, provenance_facet):
        if (
            facet.contract_version != projection.contract_version
            or facet.selected_revision_id != projection.target.law_selected_revision_id
            or facet.schema_identity != projection.schema_identity
            or facet.baseline != projection.baseline
            or facet.contributor_epoch_digest != projection.baseline.contributor_epoch_digest
            or facet.contributors != projection.contributors
        ):
            raise ValueError("graded workspace facets must retain the root consistency coordinates")
