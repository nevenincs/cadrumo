"""Live-to-local cross-validation orchestration.

This subpackage provides the synchronization engine against AEAT.
See the ADR at ``.vault/adr/2026-04-12-self-healing-sync-adr.md`` for
the architectural contract, including the bounded auto-heal invariant
and the Protocol-boundary strategy for in-flight cross-module dependencies.

Pure sync domain primitives are owned by :mod:`aeat.domain.sync`.
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
