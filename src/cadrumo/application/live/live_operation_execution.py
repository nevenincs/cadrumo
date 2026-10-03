"""Execution steps shared by registered live AEAT operations in a profile worker."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
from ...core.identity.digest import ContentDigest
from ...core.identity.profile import canonical_profile_bucket_id
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.time.clock import now
from ..operations.capabilities import OperationOwnedResource
from ..operations.models import OperationRequest
from ..operations.owner import OperationExecutorContext
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .session import LiveSessionWriteReceipt

if TYPE_CHECKING:
    from .filed_data_ports import FiledEffectGuard
    from .filed_history_operation import FiledHistoryBrowserResources, FiledHistoryBrowserResourcesFactory


def require_exact_profile_worker(profile_id: UUID, subject_ref: str, *, active_bucket_id: str) -> str:
    """Return the canonical bucket id, refusing work outside this exact profile worker.

    The caller reads ``active_bucket_id`` from the worker's bucket pointer, so a
    worker with no active profile fails before any identity comparison.
    """
    bucket_id = canonical_profile_bucket_id(profile_id)
    if active_bucket_id != bucket_id or subject_ref != profile_operation_subject(bucket_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return bucket_id


def require_live_executor_identity[PayloadT: BaseModel](
    request: OperationRequest[PayloadT], context: OperationExecutorContext, *, definition_id: str
) -> None:
    """Refuse a request this executor was not registered and invoked for."""
    if (
        request.definition_id != definition_id
        or context.identity.definition_id != request.definition_id
        or context.identity.subject_ref != request.subject_ref
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


async def own_provider_browser(
    context: OperationExecutorContext,
    browser_resources_factory: FiledHistoryBrowserResourcesFactory,
    *,
    acquire_phase: str,
) -> FiledHistoryBrowserResources:
    """Own the provider browser process before announcing remote acquisition."""
    resources = browser_resources_factory()
    context.cleanup.own(resources, family=OperationOwnedResource.PROCESS)
    await context.events.phase(acquire_phase)
    return resources


def fenced_persistence_guard(context: OperationExecutorContext, *, persist_phase: str) -> FiledEffectGuard:
    """Return the guard each local write of a remote capture enters.

    Every entry announces persistence, takes a fresh irreversible fence and only
    then marks the effect unknown, so an interrupted write is never reported as
    no change.
    """

    @asynccontextmanager
    async def guard() -> AsyncGenerator[None]:
        await context.events.phase(persist_phase)
        async with context.cancellation.irreversible_section():
            await context.events.effect(OperationEffect.UNKNOWN)
            yield

    return guard


async def publish_live_capture_report(
    context: OperationExecutorContext,
    report: BaseModel,
    *,
    result_phase: str,
    effect: OperationEffect,
) -> ContentDigest:
    """Settle the capture's effect, then store its report under a fresh fence."""
    await context.events.phase(result_phase)
    await context.events.effect(effect)
    async with context.cancellation.irreversible_section():
        return await context.operands.put(report, written_at=now())


async def publish_live_read_report(
    context: OperationExecutorContext,
    report: BaseModel,
    *,
    result_phase: str,
    effect: OperationEffect,
    task_name: str,
) -> ContentDigest:
    """Settle a read's effect, then store its report even if the caller is cancelled meanwhile."""
    await context.events.phase(result_phase)
    await context.events.effect(effect)
    return await await_cancellation_complete(context.operands.put(report, written_at=now()), task_name=task_name)


async def track_capture_session(context: OperationExecutorContext, *, may_write: bool) -> LiveSessionWriteReceipt:
    """Start tracking provider session writes for a capture.

    A capture that may write locally reports an unknown effect first, so an
    interruption before its report settles is never mistaken for no change.
    """
    if may_write:
        await context.events.effect(OperationEffect.UNKNOWN)
    return LiveSessionWriteReceipt(context.events.effect)
