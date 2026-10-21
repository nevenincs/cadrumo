"""Guarded publication of one rendered local export file by a registered operation."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from uuid import UUID

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
)
from ...core.time.clock import now
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import OperationRequest
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from .export_sink import LocalFileExportReceipt, LocalFileExportSink

#: A request-bound, non-replayable local file write whose interrupted outcome stays unknown.
LOCAL_FILE_EXPORT_CAPABILITIES = OperationCapabilities(
    durability=OperationDurability.RECORDED,
    cancellation=OperationCancellation.UNSUPPORTED,
    deadline=OperationDeadline.ABSENT,
    replay=OperationReplayPolicy.NONE,
    baseline=OperationBaselinePolicy.REQUEST_BOUND,
    request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
    sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
    conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
    owned_resources=frozenset(),
    permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN, OperationEffect.UPDATED}),
    close_policy=OperationClosePolicy.DETACH_ALLOWED,
)


async def publish_local_file_export(
    request: OperationRequest[BaseModel],
    context: OperationExecutorContext,
    *,
    profile_id: UUID,
    sink: LocalFileExportSink,
    data: bytes,
    result: Callable[[LocalFileExportReceipt], BaseModel],
    task_name: str,
) -> str:
    """Recheck admission, write the bytes and store the result inside one irreversible section.

    The effect is reported unknown before the write and updated only after it,
    and the publication runs to completion even when its caller is cancelled.
    """

    async def publish() -> str:
        async with context.cancellation.irreversible_section():
            require_operation_profile(request, context, profile_id)
            sink.require_writable()
            await context.events.effect(OperationEffect.UNKNOWN)
            receipt = await asyncio.to_thread(sink.write, data)
            await context.events.effect(OperationEffect.UPDATED)
            return await context.operands.put(result(receipt), written_at=now())

    return await await_cancellation_complete(publish(), task_name=task_name)
