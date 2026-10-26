"""Operator receipts for activity-asset inspection and claims.

Revision and claim identities are derived domain properties, so Pydantic's
serialized records omit them.  An operator correction must name the revision
it supersedes, and a later correction or filing handoff must name the claim,
so both receipts project those identities explicitly.
"""

from __future__ import annotations

from ...application.actividad_asset.history import ActivityAssetHistoryClaimResult
from ...core.errors.hierarchy import InternalInvariantError
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from ._actividad_asset_payloads import ActivityAssetClaimPayload, ActivityAssetInspectionPayload


def inspection_receipt(
    asset_id: str,
    revisions: tuple[ActivityAssetRevision, ...],
) -> ActivityAssetInspectionPayload:
    """Project each revision with the identity a correction must supersede."""
    return ActivityAssetInspectionPayload(
        asset_id=asset_id,
        revisions=[{**revision.model_dump(mode="json"), "revision_id": revision.revision_id} for revision in revisions],
    )


def claim_receipt(result: ActivityAssetHistoryClaimResult) -> ActivityAssetClaimPayload:
    """Project the recorded claim with its canonical immutable identity."""
    document = result.model_dump(mode="json")
    claim_document = document["claim"]
    if not isinstance(claim_document, dict):  # pragma: no cover - domain result invariant
        raise InternalInvariantError("activity-asset claim result must serialize a claim object")
    document["claim"] = {**claim_document, "claim_id": result.claim.claim_id}
    return ActivityAssetClaimPayload(root=document)


__all__ = ["claim_receipt", "inspection_receipt"]
