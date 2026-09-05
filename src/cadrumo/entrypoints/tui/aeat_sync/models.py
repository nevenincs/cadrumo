"""Closed routing and operation-handoff contracts for AEAT Sync."""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel

from ....application.aeat_sync.workspace import (
    AeatSyncWorkspaceNotificationRowV1,
    AeatSyncWorkspaceZone,
)
from ....application.operations.models import OperationDefinitionId
from ....application.operator_actions.models import ActionReference
from ....core.models import STRICT_FROZEN_CONFIG

type AeatSyncDestinationIdV1 = Literal[
    "aeat_sync.overview",
    "aeat_sync.census",
    "aeat_sync.filed_declarations",
    "aeat_sync.notifications",
    "aeat_sync.evidence_comparison",
    "aeat_sync.reconciliation",
]


class AeatSyncRouteTargetV1(BaseModel):
    """One internal destination selected by its stable zone identity."""

    model_config = STRICT_FROZEN_CONFIG

    destination: AeatSyncDestinationIdV1
    zone: AeatSyncWorkspaceZone


class AeatSyncOperationRequestV1(BaseModel):
    """One exact pre-admitted operation/action pair handed to the owning host."""

    model_config = STRICT_FROZEN_CONFIG

    action: ActionReference
    operation: OperationDefinitionId


class AeatSyncOperationHandoffV1(Protocol):
    """Host-owned supervisor handoff for a registered operation.

    The workspace only selects and admits the exact public action/operation
    pair.  The installed host must resolve that request to the canonical
    ``OperationController`` and present it through ``present_operation_modal``;
    that existing modal owns progress, partial/failure outcomes, detach and
    cancellation.  Implementations must not execute the operation inline.
    """

    async def __call__(self, request: AeatSyncOperationRequestV1, /) -> None:
        """Present the exact request through the host's operation supervisor."""
        ...


class AeatSyncNotificationDocumentHandoffV1(Protocol):
    """Host-owned door for one already-read notification row.

    The row carries a selection coordinate rather than the document, and that
    is a BOUNDARY, not a redaction. This workspace is a projection: it holds
    facts already loaded and scoped, and reaching storage or the AEAT for bytes
    is the host's job, behind the operation surface that owns progress, failure
    and cancellation. Retrieving a document here would put I/O inside a
    projection and bypass all three.

    Nothing is being withheld from the operator, whose document it is. The
    handoff exists so the host opens it through the surface built for that.
    """

    async def __call__(self, row: AeatSyncWorkspaceNotificationRowV1, /) -> None:
        """Present the document through the owning host boundary."""
        ...


__all__ = [
    "AeatSyncDestinationIdV1",
    "AeatSyncNotificationDocumentHandoffV1",
    "AeatSyncOperationHandoffV1",
    "AeatSyncOperationRequestV1",
    "AeatSyncRouteTargetV1",
]
