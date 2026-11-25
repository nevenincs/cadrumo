"""Best-effort wall-clock observations of committed operation transitions."""

from __future__ import annotations

from time import time_ns
from typing import Literal

from ...core.logging import get_logger
from .models import OperationIdentity

_log = get_logger(__name__)


def log_operation_timing(identity: OperationIdentity, stage: Literal["admitted", "running", "settled"]) -> None:
    """Observe a committed transition without carrying its subject or payload.

    The epoch milliseconds are sampled here, independently of the application
    clock or a receipt prepared before cleanup. ``running`` means the initial
    RUNNING commit, not worker readiness or executor completion. Delivery uses
    the shared bounded diagnostic queue; it is never a commit fence.
    """
    _log.info(
        "operation timing stage=%s epoch_ms=%d operation=%s definition=%s",
        stage,
        time_ns() // 1_000_000,
        identity.operation_id,
        identity.definition_id,
    )
