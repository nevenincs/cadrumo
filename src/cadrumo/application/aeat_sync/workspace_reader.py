"""Read the local-only AEAT Sync workspace an installed session starts from.

Every fact this workspace shows is either observed AT the AEAT or derived from
comparing local records against such an observation, and the decision that
governs this surface is explicit: initial load is local-only, and reaching the
AEAT is always an operator action with visible progress and result.

So the projection a session opens with carries no rows and says, per source,
exactly why: an AEAT authority was NEVER CAPTURED because nothing has been
pulled yet, and a local authority whose installed row reader does not exist is
UNAVAILABLE rather than rendered as an empty list. Neither is a zero, and
neither is a failure — they are the two honest reasons a zone is empty before
the first pull, and the destination stays reachable so that pull can happen.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from ..operator_actions.catalogue import OPERATOR_ACTION_CATALOGUE
from .workspace import (
    AeatSyncWorkspaceAvailability,
    AeatSyncWorkspaceProjectionV1,
    AeatSyncWorkspaceSource,
    AeatSyncWorkspaceSourceObservationV1,
    AeatSyncWorkspaceZone,
    AeatSyncWorkspaceZoneObservationV1,
    aeat_sync_workspace_sources,
    project_aeat_sync_workspace,
)

if TYPE_CHECKING:
    from ..operations.registry import OperationPublicContractSetV1

_AEAT_SOURCES: Final[frozenset[AeatSyncWorkspaceSource]] = frozenset(
    {
        AeatSyncWorkspaceSource.AEAT_CENSUS,
        AeatSyncWorkspaceSource.AEAT_FILED_DECLARATIONS,
        AeatSyncWorkspaceSource.AEAT_NOTIFICATIONS,
    }
)

_NEVER_PULLED: Final[str] = "workbench.aeat_sync.never_pulled"
_NO_LOCAL_ROW_READER: Final[str] = "workbench.aeat_sync.local_row_reader_unavailable"


def _observation(source: AeatSyncWorkspaceSource) -> AeatSyncWorkspaceSourceObservationV1:
    if source in _AEAT_SOURCES:
        return AeatSyncWorkspaceSourceObservationV1(
            source=source,
            availability=AeatSyncWorkspaceAvailability.NEVER_CAPTURED,
            refusal=_NEVER_PULLED,
        )
    return AeatSyncWorkspaceSourceObservationV1(
        source=source,
        availability=AeatSyncWorkspaceAvailability.UNAVAILABLE,
        refusal=_NO_LOCAL_ROW_READER,
    )


def read_local_aeat_sync_workspace_projection(
    *,
    bucket_id: str,
    subject_key: str,
    operation_contracts: OperationPublicContractSetV1,
) -> AeatSyncWorkspaceProjectionV1:
    """Project the pre-pull AEAT Sync workspace for one authenticated profile.

    The pull and comparison actions come from the same registered operation
    contracts the session composed, so the surface can only offer work the
    process can actually perform.
    """
    return project_aeat_sync_workspace(
        bucket_id=bucket_id,
        subject_key=subject_key,
        zone_observations=tuple(
            AeatSyncWorkspaceZoneObservationV1(
                zone=zone,
                sources=tuple(_observation(source) for source in aeat_sync_workspace_sources(zone)),
            )
            for zone in AeatSyncWorkspaceZone
        ),
        action_catalogue=OPERATOR_ACTION_CATALOGUE,
        operation_contracts=operation_contracts,
    )


__all__ = ["read_local_aeat_sync_workspace_projection"]
