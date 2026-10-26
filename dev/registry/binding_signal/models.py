"""Shared data structures passed between binding-signal audit stages."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class SupportScope:
    """The declared filing envelope and revisions unreachable below its floor."""

    floor: int
    horizon: int
    hard_ceiling: int | None
    below_floor: frozenset[tuple[str, str]]


@dataclass(slots=True)
class RawInventory:
    """Raw authored revision fragments collected in deterministic order."""

    revisions: dict[tuple[str, str], Any]
    declared_coordinates: set[tuple[str, str]]
    revisions_below_floor: list[str]
    parse_failures: list[dict[str, object]]
    modelos_without_revisions: list[str]
    family_file_counts: Counter[str]
    family_row_counts: Counter[str]


@dataclass(slots=True)
class SignalInputs:
    """Independent input surfaces used by the reverse binding audit."""

    root: Path
    registry_root: Path
    registrations: dict[str, dict[str, object]]
    compiled: dict[tuple[str, str], Any]
    support_scope: SupportScope | None
    runtime_resolvers: dict[str, dict[str, object]]
    binding_consumers: Callable[[Any], Mapping[str, Any]] | None
    limitations: list[dict[str, object]]
    raw: RawInventory
