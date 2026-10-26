"""Read census evidence from its existing operation journals and encrypted operands."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

from ...core.errors.hierarchy import InternalInvariantError
from ...core.operations import OperationTerminalCondition, profile_operation_subject
from ..operations.persistence.journal import (
    OperationJournal,
    OperationRecoveryInventoryDisposition,
    OperationSecureReferenceStore,
)
from .censal_observation import CensalObservation
from .censal_operation import CENSAL_OPERATION_DEFINITION_ID, CensalOperationResult, CensalReviewedOperand
from .censal_preview_operation import CENSAL_PREVIEW_OPERATION_DEFINITION_ID, CensalPreviewOperationResult

type CensalObservationReader = Callable[[UUID], Awaitable[CensalObservation | None]]


async def read_latest_censal_observation(
    profile_id: UUID,
    *,
    journal: OperationJournal,
    operands: OperationSecureReferenceStore,
) -> CensalObservation | None:
    """Resolve the newest successful own-profile capture, including rejected local adoption.

    A preview or a review owns its evidence already. Reading that custody avoids
    a second mutable snapshot store. Failed operations cannot replace a previous
    capture, and a historical preview without evidence is not an empty census.
    """
    latest: CensalObservation | None = None
    subjects = {
        CENSAL_OPERATION_DEFINITION_ID: str(profile_id),
        CENSAL_PREVIEW_OPERATION_DEFINITION_ID: profile_operation_subject(str(profile_id)),
    }
    after: str | None = None
    while True:
        page = await journal.inventory_page(after=after, limit=128)
        for entry in page.entries:
            if entry.disposition is OperationRecoveryInventoryDisposition.REFUSED:
                raise InternalInvariantError("census capture history cannot be verified")
            if entry.disposition is not OperationRecoveryInventoryDisposition.TERMINAL:
                continue
            snapshot = await journal.load(entry.operation_id)
            if (
                snapshot.identity.subject_ref != subjects.get(snapshot.identity.definition_id)
                or snapshot.terminal_condition is not OperationTerminalCondition.SUCCEEDED
            ):
                continue
            receipt = snapshot.terminal_receipt
            if receipt is None or receipt.result_ref is None:
                raise InternalInvariantError("settled census capture has no result reference")
            if snapshot.identity.definition_id == CENSAL_PREVIEW_OPERATION_DEFINITION_ID:
                preview = await operands.resolve(receipt.result_ref, CensalPreviewOperationResult)
                if preview.profile_id != profile_id:
                    raise InternalInvariantError("stored census preview belongs to another profile")
                observation = preview.observation
            else:
                result = await operands.resolve(receipt.result_ref, CensalOperationResult)
                reviewed = await operands.resolve(result.reviewed_proposal_digest, CensalReviewedOperand)
                if reviewed.baseline.profile_id != str(profile_id):
                    raise InternalInvariantError("stored census review belongs to another profile")
                observation = reviewed.observation
            if observation is not None and (latest is None or observation.captured_at > latest.captured_at):
                latest = observation
        if not page.has_more:
            return latest
        after = page.next_cursor
