"""Abstract base class and outcome types for sync healing strategies.

Defines the :class:`HealingStrategy` interface every concrete strategy must
implement and the :class:`StrategyOutcome` record returned by every strategy
application. Concrete strategies live alongside this module
(:class:`aeat.application.sync._strategies._benign.BenignRecordStrategy`,
:class:`aeat.application.sync._strategies._escalate.EscalateStrategy`, and the
additive-allowlist strategy) and are composed by the dispatcher in
:mod:`aeat.application.sync`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from ....domain.sync import DivergenceRecord


class StrategyAction(StrEnum):
    """Terminal action a healing strategy applied to a divergence record.

    Attributes:
        AUTO_HEALED: The strategy applied a self-healing fix without human
            intervention. Reachable only for additive divergences whose
            kind is in the operator-configured auto-heal allowlist.
        ESCALATED: The strategy refused to act and forwarded the record to
            the human review queue with ``resolution_state=PENDING``.
        RECORDED: The strategy persisted the record for audit but took no
            action. Used for benign informational deltas (e.g. filing
            status transitions) that need no follow-up.
    """

    AUTO_HEALED = "auto_healed"
    ESCALATED = "escalated"
    RECORDED = "recorded"


class StrategyOutcome(BaseModel):
    """Result of applying a single :class:`HealingStrategy` to one record.

    Attributes:
        action: The terminal :class:`StrategyAction` the strategy chose.
        record: The (possibly updated) :class:`aeat.domain.sync.DivergenceRecord`
            after the strategy ran. Strategies use ``model_copy`` to flip the
            ``resolution_state`` field rather than mutating in place.
        notes: Optional free-form annotation explaining why the strategy
            picked the action. Surfaced in audit logs.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    action: StrategyAction
    record: DivergenceRecord
    notes: str | None = None


class HealingStrategy(ABC):
    """Abstract base class for every divergence healing strategy.

    Subclasses declare the kinds of divergences they handle via
    :meth:`can_handle` and produce an outcome via :meth:`apply`. The
    dispatcher walks a tuple of strategies in priority order and invokes
    the first one whose ``can_handle`` returns ``True``.
    """

    @abstractmethod
    def can_handle(self, record: DivergenceRecord) -> bool:
        """Return whether this strategy wants to process ``record``.

        Args:
            record: The :class:`aeat.domain.sync.DivergenceRecord` under
                consideration.

        Returns:
            ``True`` when the strategy claims the record; ``False`` to defer
            to the next strategy in the dispatch chain.
        """

    @abstractmethod
    async def apply(
        self,
        record: DivergenceRecord,
        *,
        auto_heal: bool,
    ) -> StrategyOutcome:
        """Apply this strategy to ``record`` and return the resolved outcome.

        Args:
            record: The :class:`aeat.domain.sync.DivergenceRecord` to process.
            auto_heal: Whether the operator opted into auto-healing for this
                run. Strategies that never auto-heal (e.g.
                :class:`aeat.application.sync._strategies._escalate.EscalateStrategy`)
                ignore the flag.

        Returns:
            A :class:`StrategyOutcome` describing the action taken and
            carrying the updated record.
        """
