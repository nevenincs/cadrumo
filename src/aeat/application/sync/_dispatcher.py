"""Healing dispatcher: the bounded-policy gatekeeper.

Composes strategies in the order supplied and asks each whether it
wants to handle the record. The **enforced invariant** (tested
rigorously in ``test_bounded_policy.py``) is:

    auto_heal_applied ⇔
        classification == DivergenceClassification.ADDITIVE
        AND payload.kind in auto_heal_allowlist

Every other record (including every BREAKING and every SUSPICIOUS
kind) is routed to :class:`StrategyAction.ESCALATED` regardless of
the ``auto_heal`` flag.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ...core.logging import get_logger
from ._divergence import (
    DivergenceClassification,
    DivergenceKind,
    DivergenceRecord,
    ResolutionState,
)
from ._strategies import (
    AdditiveAllowlistStrategy,
    BenignRecordStrategy,
    EscalateStrategy,
    HealingStrategy,
    StrategyAction,
    StrategyOutcome,
)

_LOGGER = get_logger(__name__)


class HealingPlan(BaseModel):
    """Bucketed healing plan for a single sync run."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    auto_heal: tuple[DivergenceRecord, ...]
    escalate: tuple[DivergenceRecord, ...]
    benign: tuple[DivergenceRecord, ...]


class HealingDispatcher:
    """Dispatch divergence records through the configured strategies."""

    def __init__(
        self,
        *,
        strategies: tuple[HealingStrategy, ...],
        auto_heal_allowlist: frozenset[DivergenceKind],
    ) -> None:
        self._strategies = strategies
        self._allowlist = auto_heal_allowlist

    @property
    def auto_heal_allowlist(self) -> frozenset[DivergenceKind]:
        """Return the configured auto-heal allowlist."""
        return self._allowlist

    async def dispatch(
        self,
        records: tuple[DivergenceRecord, ...],
        *,
        auto_heal: bool,
    ) -> tuple[HealingPlan, tuple[StrategyOutcome, ...]]:
        """Run every record through the strategy chain and bucket the outcomes.

        The bounded-policy invariant is double-enforced here: even if a
        strategy were to return ``AUTO_HEALED`` for a record that is
        not both ADDITIVE and allowlisted, this method downgrades the
        outcome to ``ESCALATED`` with ``resolution_state=PENDING``.
        """
        outcomes: list[StrategyOutcome] = []
        auto_heal_bucket: list[DivergenceRecord] = []
        escalate_bucket: list[DivergenceRecord] = []
        benign_bucket: list[DivergenceRecord] = []

        for record in records:
            outcome = await self._dispatch_one(record, auto_heal=auto_heal)
            outcome = self._enforce_bounded_policy(outcome)
            outcomes.append(outcome)
            match outcome.action:
                case StrategyAction.AUTO_HEALED:
                    auto_heal_bucket.append(outcome.record)
                case StrategyAction.ESCALATED:
                    escalate_bucket.append(outcome.record)
                case StrategyAction.RECORDED:
                    benign_bucket.append(outcome.record)

        plan = HealingPlan(
            auto_heal=tuple(auto_heal_bucket),
            escalate=tuple(escalate_bucket),
            benign=tuple(benign_bucket),
        )
        return plan, tuple(outcomes)

    async def _dispatch_one(
        self,
        record: DivergenceRecord,
        *,
        auto_heal: bool,
    ) -> StrategyOutcome:
        for strategy in self._strategies:
            if strategy.can_handle(record):
                return await strategy.apply(record, auto_heal=auto_heal)
        _LOGGER.warning(
            "no strategy claimed record %s; defaulting to escalate",
            record.record_id,
        )
        return StrategyOutcome(
            action=StrategyAction.ESCALATED,
            record=record.model_copy(update={"resolution_state": ResolutionState.PENDING}),
            notes="no strategy matched",
        )

    def _enforce_bounded_policy(self, outcome: StrategyOutcome) -> StrategyOutcome:
        """Second-line defence for the bounded auto-heal invariant.

        If a strategy mistakenly returns AUTO_HEALED for a record that
        is not both ADDITIVE and allowlisted, we downgrade it to
        ESCALATED and log a WARNING.
        """
        if outcome.action != StrategyAction.AUTO_HEALED:
            return outcome
        record = outcome.record
        if record.classification == DivergenceClassification.ADDITIVE and record.payload.kind in self._allowlist:
            return outcome
        _LOGGER.error(
            "bounded-policy downgrade: refusing auto-heal for record %s (classification=%s kind=%s)",
            record.record_id,
            record.classification.value,
            record.payload.kind.value,
        )
        return StrategyOutcome(
            action=StrategyAction.ESCALATED,
            record=record.model_copy(update={"resolution_state": ResolutionState.PENDING}),
            notes="bounded-policy downgrade",
        )


__all__ = [
    "AdditiveAllowlistStrategy",
    "BenignRecordStrategy",
    "EscalateStrategy",
    "HealingDispatcher",
    "HealingPlan",
    "HealingStrategy",
    "StrategyAction",
    "StrategyOutcome",
]
