"""Benign strategy: record the divergence for audit without action."""

from __future__ import annotations

from .._divergence import DivergenceClassification, DivergenceRecord, ResolutionState
from ._base import HealingStrategy, StrategyAction, StrategyOutcome


class BenignRecordStrategy(HealingStrategy):
    """Records BENIGN divergences with ``resolution_state=AUTO_HEALED``.

    BENIGN records are informational — they describe cosmetic deltas
    (e.g. a filing status transitioning from PENDING to ACCEPTED) that
    do not affect the local authoritative state. The record is
    persisted for audit but no escalation is needed.
    """

    def can_handle(self, record: DivergenceRecord) -> bool:
        return record.classification == DivergenceClassification.BENIGN

    async def apply(
        self,
        record: DivergenceRecord,
        *,
        auto_heal: bool,
    ) -> StrategyOutcome:
        return StrategyOutcome(
            action=StrategyAction.RECORDED,
            record=record.model_copy(update={"resolution_state": ResolutionState.AUTO_HEALED}),
            notes="benign audit record",
        )
