"""Compare recorded AEIP judgments with the live event inventory."""

from __future__ import annotations

from .adjudications import AdjudicationSet
from .types import AeipInventory, StaleAdjudication

__all__ = ("detect_stale_adjudications",)


def detect_stale_adjudications(
    inventory: AeipInventory,
    adjudications: AdjudicationSet,
) -> tuple[StaleAdjudication, ...]:
    """Report adjudication entries the live corpus no longer supports.

    ``inventory`` must be the inventory built WITH ``adjudications`` applied
    (exclusions and aliases act during grouping), so that ``inventory.events``
    reflects the same slug space the adjudications were judged against.
    """
    live_pairs = {(occurrence.revision_id, occurrence.casilla_id) for occurrence in inventory.occurrences}
    live_titles = {occurrence.title for occurrence in inventory.occurrences if occurrence.title}
    live_slugs = {event.slug for event in inventory.events}
    found = [
        *_stale_exclusions(adjudications, live_pairs),
        *_stale_aliases(adjudications, live_titles),
        *_stale_chain_ids(adjudications, live_slugs),
        *_stale_splits(inventory, adjudications),
        *_stale_distinct_variants(adjudications, live_slugs),
    ]
    return tuple(sorted(found, key=lambda entry: (entry.kind, entry.detail)))


def _stale_exclusions(adjudications: AdjudicationSet, live_pairs: set[tuple[str, str]]) -> list[StaleAdjudication]:
    return [
        StaleAdjudication(
            kind="exclusion",
            detail=f"{exclusion.revision}:{exclusion.casilla} names no occurrence in the live corpus",
        )
        for exclusion in adjudications.exclusions
        if (exclusion.revision, exclusion.casilla) not in live_pairs
    ]


def _stale_aliases(adjudications: AdjudicationSet, live_titles: set[str]) -> list[StaleAdjudication]:
    return [
        StaleAdjudication(
            kind="alias",
            detail=f"slug {alias.slug!r} names no title the live corpus publishes: {alias.titles}",
        )
        for alias in adjudications.aliases
        if not any(title in live_titles for title in alias.titles)
    ]


def _stale_chain_ids(adjudications: AdjudicationSet, live_slugs: set[str]) -> list[StaleAdjudication]:
    return [
        StaleAdjudication(
            kind="chain_id",
            detail=f"chain id override names slug {override.slug!r}, which is not a live programme",
        )
        for override in adjudications.chain_ids
        if override.slug not in live_slugs
    ]


def _stale_splits(inventory: AeipInventory, adjudications: AdjudicationSet) -> list[StaleAdjudication]:
    found: list[StaleAdjudication] = []
    for split in adjudications.splits:
        event = inventory.event_by_slug(split.slug)
        if event is None:
            found.append(
                StaleAdjudication(
                    kind="split",
                    detail=f"split names slug {split.slug!r}, which is not a live programme",
                ),
            )
        elif split.from_revision not in event.revisions:
            found.append(
                StaleAdjudication(
                    kind="split",
                    detail=(
                        f"split for {split.slug!r} names revision {split.from_revision!r}, "
                        f"which is not among {event.revisions}"
                    ),
                ),
            )
    return found


def _stale_distinct_variants(adjudications: AdjudicationSet, live_slugs: set[str]) -> list[StaleAdjudication]:
    found: list[StaleAdjudication] = []
    for variants in adjudications.distinct_variants:
        missing = tuple(slug for slug in variants.slugs if slug not in live_slugs)
        if missing:
            found.append(
                StaleAdjudication(
                    kind="distinct_variants",
                    detail=f"distinct_variants names slug(s) no longer live: {missing}",
                ),
            )
    return found
