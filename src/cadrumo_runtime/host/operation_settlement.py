"""Operation inventory and settlement for a profile worker."""

from __future__ import annotations

import asyncio
from math import isfinite
from time import monotonic
from typing import TYPE_CHECKING

from cadrumo.adapters.persistence.storage.errors import RepositoryError
from cadrumo.application.operations.errors import OperationUnsettledError
from cadrumo.application.operations.models import (
    OperationId,
    OperationIdentity,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.logging import get_logger
from cadrumo.core.operations import OperationLifecycle
from cadrumo_client.contracts.access_refusals import AccessDenialCode

if TYPE_CHECKING:
    from cadrumo.application.operations.supervisor import OperationSupervisor

    from .operation_host import ProfileWorkerOperationHost

_LAPSE_CHECK_SECONDS = 30.0
_log = get_logger(__name__)


async def verify_inventory(host: ProfileWorkerOperationHost) -> None:
    """Verify and retain the current durable recovery inventory."""
    async with host.inventory_lock:
        if host.inventory_verified:
            return
        services = await host.composed_off_loop()
        from cadrumo.application.operations.persistence.journal import OperationRecoveryInventoryDisposition

        after = None
        refused = False
        unsettled: set[OperationId] = set()
        try:
            while True:
                page = await services.recovery_inventory(after=after, limit=128)
                refused |= any(
                    entry.disposition is OperationRecoveryInventoryDisposition.REFUSED for entry in page.entries
                )
                unsettled.update(
                    entry.operation_id
                    for entry in page.entries
                    if entry.disposition is OperationRecoveryInventoryDisposition.NONTERMINAL
                )
                if not page.has_more:
                    break
                after = page.next_cursor
        except (RepositoryError, ValueError):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE) from None
        if refused or host.closed:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        host.unsettled.update(unsettled)
        host.inventory_verified = True


async def settle_lapsed_operations(host: ProfileWorkerOperationHost) -> None:
    """Settle every operation whose owner stopped renewing its lease and whose grace has passed.

    Its owner is gone, and its submitter has had a whole lease to continue
    it, so nothing else would ever settle it. Checked at most every
    :data:`_LAPSE_CHECK_SECONDS` as the profile is used; a failure is logged
    with the operation and never refuses the caller's own request.
    """
    now = monotonic()
    checked_at = host.lapse_checked_at
    if host.lapse_lock.locked() or (checked_at is not None and now - checked_at < _LAPSE_CHECK_SECONDS):
        return
    async with host.lapse_lock:
        host.lapse_checked_at = now
        supervisor = host.composed().submission.supervisor
        for operation_id in sorted(host.unsettled):
            try:
                settled = await supervisor.settle_lapsed(operation_id, grace=supervisor.lease_duration)
            except (RepositoryError, ValueError) as error:
                _log.warning(
                    "lapsed operation left unsettled operation=%s error=%s", operation_id, type(error).__name__
                )
                continue
            if settled is not None and settled.lifecycle is OperationLifecycle.TERMINAL:
                host.unsettled.discard(operation_id)


async def settlement(host: ProfileWorkerOperationHost, identity: OperationIdentity, *, timeout: float) -> bool:
    """Wait for an original rotation's terminal journal without old-key disclosure.

    Timeout cancels only this waiter. The canonical supervisor shields its
    settlement task, which remains owned until it terminates or is drained.
    A terminal failure is settled too; this acknowledgment claims no
    successful domain effect or available private result.
    """
    supervisor = _settlement_supervisor(host, identity, timeout)
    return await _await_settlement(host, supervisor, identity, timeout)


def _settlement_supervisor(
    host: ProfileWorkerOperationHost, identity: OperationIdentity, timeout: float
) -> OperationSupervisor:
    from cadrumo.application.auth.operation_definitions import PROFILE_ROTATION_OPERATION_DEFINITION_ID

    original = host.submissions.get(identity.operation_id)
    services = host.services
    if (
        host.closed
        or services is None
        or original is None
        or original[1].receipt.operation_id != identity.operation_id
        or identity.definition_id != PROFILE_ROTATION_OPERATION_DEFINITION_ID
        or not isfinite(timeout)
        or not 0 < timeout <= 5
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    return services.submission.supervisor


async def _await_settlement(
    host: ProfileWorkerOperationHost, supervisor: OperationSupervisor, identity: OperationIdentity, timeout: float
) -> bool:
    wait = asyncio.timeout(timeout)
    try:
        async with wait:
            observed = await supervisor.inspect(identity.operation_id)
            if observed.identity != identity:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            terminal = await supervisor.settled(identity.operation_id)
            if terminal.identity != identity or terminal.lifecycle is not OperationLifecycle.TERMINAL:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            return True
    except TimeoutError:
        if wait.expired():
            return False
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE) from None
    except (RepositoryError, OperationUnsettledError, KeyError, ValueError):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE) from None
