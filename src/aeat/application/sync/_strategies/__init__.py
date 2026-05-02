"""Healing strategy implementations for the sync runner.

Re-exports the strategy ABC :class:`HealingStrategy`, the outcome
records :class:`StrategyAction` and :class:`StrategyOutcome`, and the
three concrete strategies the dispatcher composes:
:class:`AdditiveAllowlistStrategy`, :class:`BenignRecordStrategy`, and
:class:`EscalateStrategy`.
"""

from __future__ import annotations

from ._additive_allowlist import AdditiveAllowlistStrategy
from ._base import HealingStrategy, StrategyAction, StrategyOutcome
from ._benign import BenignRecordStrategy
from ._escalate import EscalateStrategy

__all__ = [
    "AdditiveAllowlistStrategy",
    "BenignRecordStrategy",
    "EscalateStrategy",
    "HealingStrategy",
    "StrategyAction",
    "StrategyOutcome",
]
