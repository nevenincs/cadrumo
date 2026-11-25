"""The catalogue entries a lane offers now, from the agent's declared and live catalogues.

The declared catalogue is always readable. While an agent runs, its live
catalogue lists the lane's models too, adding the ones installed on a local
server. A model both list is taken from the live catalogue, whose facts
describe what this computer actually holds. Without a live catalogue only the
declared entries are offered.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..domain.catalog import CatalogModelFacts, ProviderCatalogEntry
from .ports import LiveCatalogModels


def merged_entries(
    declared: Iterable[CatalogModelFacts], live: Iterable[CatalogModelFacts] | None
) -> tuple[CatalogModelFacts, ...]:
    """Return the live entries, then each declared entry the live ones do not list.

    ``live`` is ``None`` when there is no live catalogue; then the declared
    entries are returned as they are. A model a source lists twice keeps its
    first entry.
    """
    merged: dict[str, CatalogModelFacts] = {}
    for entry in (*(() if live is None else live), *declared):
        merged.setdefault(entry.id, entry)
    return tuple(merged.values())


def current_lane_entries(entry: ProviderCatalogEntry, live: LiveCatalogModels) -> tuple[CatalogModelFacts, ...]:
    """Return the entries ``entry``'s lane offers now: its live ones while an agent runs, and its declared ones."""
    return merged_entries(entry.models, live.lane_models(entry.provider, entry.transport.value))


__all__ = ["current_lane_entries", "merged_entries"]
