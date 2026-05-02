"""Bounded auto-heal strategy: applies only to additive, allowlisted divergences.

Defines :class:`AdditiveAllowlistStrategy`, the only strategy that is
ever permitted to mutate local state by returning
:attr:`StrategyAction.AUTO_HEALED`.
"""

from __future__ import annotations

from ....domain.sync import (
    DivergenceClassification,
    DivergenceKind,
    DivergenceRecord,
    ResolutionState,
)
from ._base import HealingStrategy, StrategyAction, StrategyOutcome


class AdditiveAllowlistStrategy(HealingStrategy):
    """Auto-heals divergences that are BOTH additive AND allowlisted.

    This is the *only* strategy that ever returns
    :attr:`StrategyAction.AUTO_HEALED`. The bounded-heal invariant is
    encoded as two explicit guards:

    1. ``record.classification == DivergenceClassification.ADDITIVE``
    2. ``record.payload.kind in self._allowlist``

    Any record that fails either guard falls through to the escalate
    path with ``resolution_state=PENDING``. Even with ``auto_heal=True``
    the dispatcher NEVER mutates local state for a non-additive or
    non-allowlisted record.

    Attributes:
        allowlist: The set of :class:`DivergenceKind` values eligible
            for auto-heal application.
    """

    def __init__(self, allowlist: frozenset[DivergenceKind]) -> None:
        self._allowlist = allowlist

    @property
    def allowlist(self) -> frozenset[DivergenceKind]:
        """Return the frozenset of allowlisted divergence kinds."""
        return self._allowlist

    def can_handle(self, record: DivergenceRecord) -> bool:
        """Return ``True`` for additive records; defer to the dispatcher otherwise."""
        return record.classification == DivergenceClassification.ADDITIVE

    async def apply(
        self,
        record: DivergenceRecord,
        *,
        auto_heal: bool,
    ) -> StrategyOutcome:
        """Apply the bounded auto-heal guards and return the outcome."""
        if not auto_heal:
            return StrategyOutcome(
                action=StrategyAction.ESCALATED,
                record=record.model_copy(update={"resolution_state": ResolutionState.PENDING}),
                notes="auto_heal flag disabled",
            )
        if record.payload.kind not in self._allowlist:
            return StrategyOutcome(
                action=StrategyAction.ESCALATED,
                record=record.model_copy(update={"resolution_state": ResolutionState.PENDING}),
                notes=f"kind {record.payload.kind.value} not in auto-heal allowlist",
            )
        if record.classification != DivergenceClassification.ADDITIVE:
            return StrategyOutcome(
                action=StrategyAction.ESCALATED,
                record=record.model_copy(update={"resolution_state": ResolutionState.PENDING}),
                notes="classification not ADDITIVE",
            )
        return StrategyOutcome(
            action=StrategyAction.AUTO_HEALED,
            record=record.model_copy(update={"resolution_state": ResolutionState.AUTO_HEALED}),
            notes="bounded auto-heal applied",
        )
