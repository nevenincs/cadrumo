"""Escalate strategy: always emit a PENDING divergence record."""

from __future__ import annotations

from .._divergence import DivergenceRecord, ResolutionState
from ._base import HealingStrategy, StrategyAction, StrategyOutcome


class EscalateStrategy(HealingStrategy):
    """Fallback strategy that never auto-applies; always escalates to human.

    Used for every BREAKING and every SUSPICIOUS record, and for every
    ADDITIVE record whose kind is not in the auto-heal allowlist.
    """

    def can_handle(self, record: DivergenceRecord) -> bool:
        return True

    async def apply(
        self,
        record: DivergenceRecord,
        *,
        auto_heal: bool,
    ) -> StrategyOutcome:
        return StrategyOutcome(
            action=StrategyAction.ESCALATED,
            record=record.model_copy(update={"resolution_state": ResolutionState.PENDING}),
            notes="escalated for human review",
        )
