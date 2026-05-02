"""Healing strategy that audits benign divergences without taking action.

Implements the :class:`aeat.application.sync._strategies._base.HealingStrategy`
contract for divergences classified as
:attr:`aeat.domain.sync.DivergenceClassification.BENIGN` — cosmetic deltas
that need a permanent audit trail but no escalation.
"""

from __future__ import annotations

from ....domain.sync import DivergenceClassification, DivergenceRecord, ResolutionState
from ._base import HealingStrategy, StrategyAction, StrategyOutcome


class BenignRecordStrategy(HealingStrategy):
    """Persist benign divergences as audit records without escalating.

    Benign records describe cosmetic deltas (for example a filing status
    transitioning from ``PENDING`` to ``ACCEPTED``) that do not affect the
    local authoritative state. The strategy stamps the record with
    :attr:`aeat.domain.sync.ResolutionState.AUTO_HEALED` and emits a
    :attr:`aeat.application.sync._strategies._base.StrategyAction.RECORDED`
    outcome so the dispatcher persists it for audit without forwarding it
    to the human review queue.
    """

    def can_handle(self, record: DivergenceRecord) -> bool:
        """Return whether ``record`` carries a benign classification.

        Args:
            record: The candidate divergence record.

        Returns:
            ``True`` when ``record.classification`` is
            :attr:`aeat.domain.sync.DivergenceClassification.BENIGN`.
        """
        return record.classification == DivergenceClassification.BENIGN

    async def apply(
        self,
        record: DivergenceRecord,
        *,
        auto_heal: bool,
    ) -> StrategyOutcome:
        """Stamp the record as auto-healed and return a ``RECORDED`` outcome.

        Args:
            record: The benign :class:`aeat.domain.sync.DivergenceRecord`.
            auto_heal: Ignored. Benign records are always recorded
                regardless of the operator's auto-heal preference because
                they require no remediation.

        Returns:
            A :class:`aeat.application.sync._strategies._base.StrategyOutcome`
            with the record's ``resolution_state`` updated to
            :attr:`aeat.domain.sync.ResolutionState.AUTO_HEALED`.
        """
        return StrategyOutcome(
            action=StrategyAction.RECORDED,
            record=record.model_copy(update={"resolution_state": ResolutionState.AUTO_HEALED}),
            notes="benign audit record",
        )
