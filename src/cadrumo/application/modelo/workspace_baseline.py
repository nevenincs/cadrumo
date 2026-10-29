"""Read consistency identity assembled from captured Workspace coordinates."""

from __future__ import annotations

from ...core.hashing import content_hash_hex
from .workspace_models import (
    ModeloWorkspaceBaselineV1,
    ModeloWorkspaceLocaleSummaryV1,
    ModeloWorkspaceResolvedTargetV1,
    ModeloWorkspaceSchemaIdentityV1,
)
from .workspace_producers import ModeloWorkspaceEpochV1, ModeloWorkspaceProducerStampV1


def resolve_workspace_baseline(
    target: ModeloWorkspaceResolvedTargetV1,
    *,
    schema_identity: ModeloWorkspaceSchemaIdentityV1,
    locale: ModeloWorkspaceLocaleSummaryV1,
    stamps: tuple[ModeloWorkspaceProducerStampV1, ...],
    epochs: tuple[ModeloWorkspaceEpochV1, ...],
) -> ModeloWorkspaceBaselineV1:
    """Digest the caller's captured coordinates in their admission-specific order.

    The caller validates currentness before assembly. This function captures
    nothing and preserves the supplied stamp and epoch ordering.
    """
    contributor_stamp_digest = content_hash_hex([stamp.model_dump(mode="json") for stamp in stamps])
    contributor_epoch_digest = content_hash_hex([epoch.model_dump(mode="json") for epoch in epochs])
    token = content_hash_hex(
        {
            "contributor_stamp_digest": contributor_stamp_digest,
            "contributor_epoch_digest": contributor_epoch_digest,
            "target": target.model_dump(mode="json"),
            "selected_revision_id": target.law_selected_revision_id,
            "schema_identity": schema_identity.model_dump(mode="json"),
            "locale_catalogue_digest": locale.catalogue_digest,
        }
    )
    return ModeloWorkspaceBaselineV1(
        token=token,
        contributor_stamp_digest=contributor_stamp_digest,
        contributor_epoch_digest=contributor_epoch_digest,
        target=target,
        selected_revision_id=target.law_selected_revision_id,
        schema_identity=schema_identity,
        locale_catalogue_digest=locale.catalogue_digest,
    )
