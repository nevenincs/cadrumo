"""Healing strategy that escalates every divergence for human review.

Implements the catch-all leaf of the dispatch chain in
:mod:`aeat.application.sync`. Always claims the record and forwards it to the
human review queue with
:attr:`aeat.domain.sync.ResolutionState.PENDING`.
"""

from __future__ import annotations

from ....domain.sync import DivergenceRecord, ResolutionState
from ._base import HealingStrategy, StrategyAction, StrategyOutcome


class EscalateStrategy(HealingStrategy):
    """Catch-all strategy that escalates every record for human review.

    The strategy never auto-applies and is intended as the last entry in
    the dispatcher's strategy tuple. It handles every breaking and
    suspicious record, plus every additive record whose kind is not in the
    operator-configured auto-heal allowlist.
    """

    def can_handle(self, record: DivergenceRecord) -> bool:
        """Always claim the record.

        Args:
            record: The candidate divergence record.

        Returns:
            ``True``. The escalate strategy is the final fallback; it must
            accept any record that earlier strategies declined.
        """
        return True

    async def apply(
        self,
        record: DivergenceRecord,
        *,
        auto_heal: bool,
    ) -> StrategyOutcome:
        """Stamp the record ``PENDING`` and emit an ``ESCALATED`` outcome.

        Args:
            record: The :class:`aeat.domain.sync.DivergenceRecord` to escalate.
            auto_heal: Ignored. Escalation is unconditional regardless of
                the operator's auto-heal preference.

        Returns:
            A :class:`aeat.application.sync._strategies.StrategyOutcome`
            with the record's ``resolution_state`` updated to
            :attr:`aeat.domain.sync.ResolutionState.PENDING`.
        """
        return StrategyOutcome(
            action=StrategyAction.ESCALATED,
            record=record.model_copy(update={"resolution_state": ResolutionState.PENDING}),
            notes="escalated for human review",
        )
