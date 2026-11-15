"""Bounded INFO observations of advisory operation cue delivery."""

from __future__ import annotations

import logging
from threading import Lock
from time import monotonic_ns, time_ns
from typing import Literal

from cadrumo.application.operations.models import OperationId
from cadrumo.core.diagnostic_log import diagnostic_event
from cadrumo.core.logging import get_logger

_LOGGER = get_logger(__name__)
_MAX_LINES_PER_OPERATION = 32
_MAX_TRACKED_OPERATIONS = 1024
_line_counts: dict[OperationId, int] = {}
_budget_lock = Lock()

type CueTimingStage = Literal[
    "commit_observed",
    "report_send",
    "report_send_returned",
    "report_unacknowledged",
    "parent_received",
    "fanout_start",
    "publish_cues_complete",
    "parent_ack_written",
    "worker_ack_received",
]


def _is_opaque_operation_id(identifier: OperationId) -> bool:
    return len(identifier) == 64 and all(character in "0123456789abcdef" for character in identifier)


def _claim_identifiers(operation_ids: tuple[OperationId, ...]) -> tuple[OperationId, ...]:
    """Claim bounded diagnostic slots without waiting or resetting old budgets."""
    identifiers = dict.fromkeys(identifier for identifier in operation_ids[:4] if _is_opaque_operation_id(identifier))
    if not identifiers or not _budget_lock.acquire(blocking=False):
        return ()
    claimed: list[OperationId] = []
    try:
        for identifier in identifiers:
            count = _line_counts.get(identifier, 0)
            if count >= _MAX_LINES_PER_OPERATION:
                continue
            if count == 0 and len(_line_counts) >= _MAX_TRACKED_OPERATIONS:
                continue
            _line_counts[identifier] = count + 1
            claimed.append(identifier)
    finally:
        _budget_lock.release()
    return tuple(claimed)


def log_operation_cue_timing(
    stage: CueTimingStage,
    operation_ids: tuple[OperationId, ...],
    *,
    cue_attempt_count: int | None = None,
    primary_error: BaseException | None = None,
) -> None:
    """Observe a stage without turning diagnostics into a delivery fence.

    Epoch time joins process logs; monotonic time measures intervals. Only four
    opaque operation identifiers are retained, with explicit batch truncation.
    Commit observation is the callback entry, not a durable journal timestamp.
    Publication completion means the fanout attempts returned, not that any
    cue was queued, signalled, framed or received. Its count can be zero.
    Parent ACK written and worker ACK received are distinct observations.
    This cohort records at most 32 lines per operation per process, retaining
    at most 1024 operation budgets. Contention or exhaustion drops diagnostics
    only; no budget is evicted, reset or used to control cue delivery.
    """
    try:
        if not _LOGGER.isEnabledFor(logging.INFO):
            return
        bounded = _claim_identifiers(operation_ids)
        if not bounded:
            return
        epoch_ms = time_ns() // 1_000_000
        ticks = monotonic_ns()
        attempts = "" if cue_attempt_count is None else f" cue_attempt_count={cue_attempt_count}"
        diagnostic_event(
            _LOGGER,
            f"operation cue timing stage={stage} epoch_ms={epoch_ms} monotonic_ns={ticks} "
            f"operation_ids={','.join(bounded)} batch_count={len(operation_ids)} "
            f"truncated={len(operation_ids) > len(bounded)}{attempts}",
            level=logging.INFO,
            primary_error=primary_error,
        )
    except Exception:
        return
    except BaseException:
        if primary_error is None:
            raise
