"""Stable progress, phase, and refusal contracts for filed-history workflows."""

from __future__ import annotations

from typing import Protocol

from ...core.operations import OperationEffect
from ..operations.events import OperationEventCode, OperationLogSeverity
from ..operations.models import OperationDiagnosticReference

FILED_HISTORY_PHASE_DISCOVERY = "filed-history.discovery"
FILED_HISTORY_PHASE_REGISTER_ACCESS = "filed-history.register-access"
FILED_HISTORY_PHASE_PAIR_WALK = "filed-history.pair-walk"
FILED_HISTORY_PHASE_DECLARATION_CAPTURE = "filed-history.declaration-capture"
FILED_HISTORY_PHASE_PERSISTENCE = "filed-history.persistence"
FILED_HISTORY_PHASE_FINALIZATION = "filed-history.finalization"
FILED_HISTORY_PHASE_PROVENANCE = "filed-history.provenance"
FILED_HISTORY_PHASE_IVA_WALLET = "filed-history.iva-wallet"
FILED_HISTORY_PHASE_NOTIFICATIONS = "filed-history.notifications"
FILED_HISTORY_PAIR_PROGRESS_UNIT = "filed-history.pair"
FILED_HISTORY_DECLARATION_PROGRESS_UNIT = "filed-history.declaration"
FILED_HISTORY_PAIR_REFUSAL_CODE = "filed-history.refusal.pair"
FILED_HISTORY_DECLARATION_REFUSAL_CODE = "filed-history.refusal.declaration"
FILED_HISTORY_DISCOVERY_REFUSAL_CODE = "filed-history.refusal.discovery"
FILED_HISTORY_IVA_WALLET_REFUSAL_CODE = "filed-history.refusal.iva-wallet"
FILED_HISTORY_NOTIFICATIONS_REFUSAL_CODE = "filed-history.refusal.notifications"
FILED_HISTORY_STAGE_REFUSAL_CODE = "filed-history.refusal.stage"


class FiledHistoryEventSink(Protocol):
    """Receive the operation facts a supervised filed-history pull publishes.

    Declares only the emitter capabilities filed history uses, so callers that
    compose the pull need not depend on the executor-owned emitter contract;
    the supervisor's operation event emitter satisfies it structurally.
    """

    async def phase(self, phase_code: OperationEventCode) -> None:
        """Publish a transition to a definition-declared phase."""
        ...

    async def progress(
        self,
        *,
        completed: int,
        total: int,
        unit_code: OperationEventCode | None = None,
    ) -> None:
        """Publish bounded unit progress."""
        del unit_code

    async def log(
        self,
        *,
        code: OperationEventCode,
        severity: OperationLogSeverity,
        diagnostic_ref: OperationDiagnosticReference | None = None,
    ) -> None:
        """Publish a structured safe-log fact without prose or exceptions."""
        ...

    async def effect(self, effect: OperationEffect) -> None:
        """Publish the executor's current truthful effect fact."""
        ...


async def emit_filed_history_phase(events: FiledHistoryEventSink | None, phase: str) -> None:
    """Publish one operation-declared phase when the composed pull is supervised."""
    if events is not None:
        await events.phase(phase)


async def emit_filed_history_progress(
    events: FiledHistoryEventSink | None,
    *,
    completed: int,
    total: int,
    unit_code: str,
) -> None:
    """Publish one bounded safe unit counter without retaining filing identity."""
    if events is not None:
        await events.progress(completed=completed, total=total, unit_code=unit_code)


async def emit_filed_history_refusal(events: FiledHistoryEventSink | None, code: str) -> None:
    """Publish only a stable failure scope, never local exception prose."""
    if events is not None:
        await events.log(code=code, severity=OperationLogSeverity.WARNING)


__all__ = [
    "FILED_HISTORY_DECLARATION_PROGRESS_UNIT",
    "FILED_HISTORY_DECLARATION_REFUSAL_CODE",
    "FILED_HISTORY_DISCOVERY_REFUSAL_CODE",
    "FILED_HISTORY_IVA_WALLET_REFUSAL_CODE",
    "FILED_HISTORY_NOTIFICATIONS_REFUSAL_CODE",
    "FILED_HISTORY_PAIR_PROGRESS_UNIT",
    "FILED_HISTORY_PAIR_REFUSAL_CODE",
    "FILED_HISTORY_PHASE_DECLARATION_CAPTURE",
    "FILED_HISTORY_PHASE_DISCOVERY",
    "FILED_HISTORY_PHASE_FINALIZATION",
    "FILED_HISTORY_PHASE_IVA_WALLET",
    "FILED_HISTORY_PHASE_NOTIFICATIONS",
    "FILED_HISTORY_PHASE_PAIR_WALK",
    "FILED_HISTORY_PHASE_PERSISTENCE",
    "FILED_HISTORY_PHASE_PROVENANCE",
    "FILED_HISTORY_PHASE_REGISTER_ACCESS",
    "FILED_HISTORY_STAGE_REFUSAL_CODE",
    "FiledHistoryEventSink",
    "emit_filed_history_phase",
    "emit_filed_history_progress",
    "emit_filed_history_refusal",
]
