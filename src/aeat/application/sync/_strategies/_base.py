"""Healing strategy ABC and strategy outcome types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from .._divergence import DivergenceRecord


class StrategyAction(StrEnum):
    """What a strategy decided to do with a divergence record."""

    AUTO_HEALED = "auto_healed"
    ESCALATED = "escalated"
    RECORDED = "recorded"


class StrategyOutcome(BaseModel):
    """The outcome of applying a strategy to a single divergence record."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    action: StrategyAction
    record: DivergenceRecord
    notes: str | None = None


class HealingStrategy(ABC):
    """Abstract base for every healing strategy."""

    @abstractmethod
    def can_handle(self, record: DivergenceRecord) -> bool:
        """Return ``True`` iff this strategy wants to process ``record``."""

    @abstractmethod
    async def apply(
        self,
        record: DivergenceRecord,
        *,
        auto_heal: bool,
    ) -> StrategyOutcome:
        """Apply this strategy to ``record`` and return the outcome."""
