"""Live-to-local cross-validation orchestration.

This subpackage drives the synchronization engine against AEAT,
enforcing a bounded auto-heal invariant and routing in-flight
cross-module dependencies through narrow :class:`typing.Protocol`
boundaries. Pure sync domain primitives are owned by
:mod:`aeat.domain.sync`.
"""

from __future__ import annotations

from ._dispatcher import HealingDispatcher, HealingPlan
from ._repository import (
    DivergenceRecordRepository,
    JsonFileDivergenceRepository,
)
from ._runner import LivePayloadFetcher, LiveSyncRunner, SyncRunResult
from ._strategies import (
    AdditiveAllowlistStrategy,
    BenignRecordStrategy,
    EscalateStrategy,
    HealingStrategy,
    StrategyAction,
    StrategyOutcome,
)

__all__ = [
    "AdditiveAllowlistStrategy",
    "BenignRecordStrategy",
    "DivergenceRecordRepository",
    "EscalateStrategy",
    "HealingDispatcher",
    "HealingPlan",
    "HealingStrategy",
    "JsonFileDivergenceRepository",
    "LivePayloadFetcher",
    "LiveSyncRunner",
    "StrategyAction",
    "StrategyOutcome",
    "SyncRunResult",
]
