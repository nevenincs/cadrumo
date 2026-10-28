"""Bounded worker-activity observations during an idle fence."""

from __future__ import annotations

from collections.abc import Callable

from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo_client.contracts.automation_codes import AutomationCustodyError
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError

from ..adapters.profile_worker import ProfileWorkerProcess


def observe_worker_activity(
    worker: ProfileWorkerProcess, *, deadline: float, worker_exited: Callable[[ProfileWorkerProcess], None]
) -> int | None:
    """Report unknown on an unanswered probe, fencing a failed worker."""
    try:
        # An unanswered probe reports unknown and leaves a busy worker
        # alive. Its late answer is discarded, never reused as proof that a
        # subsequent admission fence was idle.
        activity = worker.activity(deadline=deadline)
    except RefusalError as error:
        # The probe fences a worker whose channel failed; that is a loss, not an unknown count.
        if error.reason is not RefusalCode.TIMEOUT and worker.stopping:
            worker_exited(worker)
        return None
    except (AutomationCustodyError, ProfileAccessRefusedError):
        return None
    return None if activity is None else activity.in_flight_operations
