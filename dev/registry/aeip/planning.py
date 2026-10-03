"""Plan fail-closed event-keyed AEIP continuity chains and source-backed records."""

from __future__ import annotations

import re
from collections import defaultdict
from itertools import pairwise

from .adjudications import AdjudicationSet
from .errors import AeipError
from .identity import CHAIN_ID_MAX_LENGTH, _normalise, chain_id_for, chain_id_is_wellformed
from .types import AeipAmbiguity, AeipEvent, AeipInventory, AeipOccurrence, ChainPlan, ChainPlanEntry, EvolutionPair

__all__ = ("plan_chains", "render_evolution_record")

_YEAR_TOKEN = re.compile(r"(19|20)\d{2}")


def _is_contiguous(revision_ids: list[str], order: dict[str, int]) -> bool:
    indexes = sorted(order[revision_id] for revision_id in set(revision_ids))
    return indexes == list(range(indexes[0], indexes[0] + len(indexes)))


def _segments_for(
    event: AeipEvent,
    adjudications: AdjudicationSet,
    order: dict[str, int],
) -> list[tuple[str, list[AeipOccurrence]]]:
    """Partition an event's occurrences into the chains it should become.

    Without a split adjudication that is one chain. With one, the occurrences
    from the adjudicated resumption revision onward become a second chain.
    """
    ordered = sorted(event.occurrences, key=lambda occurrence: order[occurrence.revision_id])
    base_chain_id = adjudications.chain_id_for(event.slug) or chain_id_for(event.slug)
    split = adjudications.split_for(event.slug)
    if split is None:
        return [(base_chain_id, ordered)]

    boundary = order.get(split.from_revision)
    if boundary is None:
        raise AeipError(
            f"split for {event.slug!r} names revision {split.from_revision!r}, which is not among {tuple(order)}",
        )
    segments: list[tuple[str, list[AeipOccurrence]]] = []
    earlier = [row for row in ordered if order[row.revision_id] < boundary]
    later = [row for row in ordered if order[row.revision_id] >= boundary]
    if earlier:
        segments.append((base_chain_id, earlier))
    if later:
        segments.append((split.chain_id, later))
    return segments


def _detect_ambiguities(
    inventory: AeipInventory,
    adjudications: AdjudicationSet,
) -> tuple[AeipAmbiguity, ...]:
    found: list[AeipAmbiguity] = []
    order = {revision: index for index, revision in enumerate(inventory.revisions)}
    found.extend(_missing_title_ambiguities(inventory))
    for event in inventory.events:
        found.extend(_event_ambiguities(event, adjudications, order))
    found.extend(_title_variant_ambiguities(inventory, adjudications))
    return tuple(sorted(found, key=lambda ambiguity: (ambiguity.kind, ambiguity.slugs)))


def _missing_title_ambiguities(inventory: AeipInventory) -> list[AeipAmbiguity]:
    return [
        AeipAmbiguity(
            kind="missing_title",
            slugs=(f"{occurrence.revision_id}:{occurrence.casilla_id}",),
            detail=(
                f"casilla {occurrence.casilla_id} in revision {occurrence.revision_id} "
                f"resolves no programme title from {occurrence.localization_keys or ('no locale key',)}, "
                "so it cannot be keyed to an event"
            ),
        )
        for occurrence in inventory.untitled_occurrences
    ]


def _event_ambiguities(
    event: AeipEvent,
    adjudications: AdjudicationSet,
    order: dict[str, int],
) -> list[AeipAmbiguity]:
    return [
        *_gapped_span_ambiguities(event, adjudications, order),
        *_duplicate_occurrence_ambiguities(event),
        *_chain_id_ambiguities(event, adjudications),
    ]


def _gapped_span_ambiguities(
    event: AeipEvent,
    adjudications: AdjudicationSet,
    order: dict[str, int],
) -> list[AeipAmbiguity]:
    found: list[AeipAmbiguity] = []
    for chain_id, rows in _segments_for(event, adjudications, order):
        if _is_contiguous([row.revision_id for row in rows], order):
            continue
        spans = ", ".join(sorted({row.revision_id for row in rows}))
        found.append(
            AeipAmbiguity(
                kind="gapped_span",
                slugs=(event.slug,),
                detail=(
                    f"{event.title!r} would be chained as {chain_id!r} across {spans}, which spans a gap; "
                    "a re-designated programme needs a split at the resumption revision"
                ),
            ),
        )
    return found


def _duplicate_occurrence_ambiguities(event: AeipEvent) -> list[AeipAmbiguity]:
    per_revision: dict[str, list[str]] = defaultdict(list)
    for occurrence in event.occurrences:
        per_revision[occurrence.revision_id].append(occurrence.casilla_id)
    return [
        AeipAmbiguity(
            kind="intra_revision_duplicate",
            slugs=(event.slug,),
            detail=(
                f"{event.title!r} occupies ids {sorted(casilla_ids)} in revision {revision_id}; "
                "adjudicate which is authoritative and exclude the other"
            ),
        )
        for revision_id, casilla_ids in sorted(per_revision.items())
        if len(casilla_ids) > 1
    ]


def _chain_id_ambiguities(event: AeipEvent, adjudications: AdjudicationSet) -> list[AeipAmbiguity]:
    if not event.spans_multiple_revisions:
        return []
    chain_id = adjudications.chain_id_for(event.slug) or chain_id_for(event.slug)
    if len(chain_id) > CHAIN_ID_MAX_LENGTH:
        detail = (
            f"chain id for {event.title!r} is {len(chain_id)} characters "
            f"(limit {CHAIN_ID_MAX_LENGTH}); adjudicate a shortened slug"
        )
    elif not chain_id_is_wellformed(chain_id):
        detail = f"chain id {chain_id!r} does not satisfy the continuidad_id pattern"
    else:
        return []
    return [AeipAmbiguity(kind="oversize_chain_id", slugs=(event.slug,), detail=detail)]


def _title_variant_ambiguities(
    inventory: AeipInventory,
    adjudications: AdjudicationSet,
) -> list[AeipAmbiguity]:
    # Two titles that differ only in an embedded year may be one programme
    # relabelled or two successive designations; the distinction is legal.
    masked: dict[str, list[AeipEvent]] = defaultdict(list)
    for event in inventory.events:
        masked[_YEAR_TOKEN.sub("Y", _normalise(event.title))].append(event)
    found: list[AeipAmbiguity] = []
    for variants in masked.values():
        if len(variants) < 2:
            continue
        slugs = tuple(event.slug for event in variants)
        if adjudications.variants_resolved(slugs):
            continue
        found.append(
            AeipAmbiguity(
                kind="title_variant",
                slugs=slugs,
                detail=(
                    "titles differ only by an embedded year: "
                    + " | ".join(f"{event.title!r} ({', '.join(event.revisions)})" for event in variants)
                    + "; adjudicate one relabelled programme (alias) or successive designations (keep apart)"
                ),
            ),
        )
    return found


def _classify_pair(earlier: AeipOccurrence, later: AeipOccurrence) -> str:
    """Name the evolution kind for one adjacent-revision pair.

    An anexo-A event row declares no structural core, so the two axes that can
    drift are the published label and the legal refs. Both must be compared:
    the 2025 revision adds an ordinal reference to every row in the family, so
    a pair crossing that boundary really has evolved its legal refs, and
    recording it as ``unchanged`` would be a drift the strict cross-revision
    validator refuses. A retirement is planned separately.
    """
    label_moved = _normalise(earlier.label) != _normalise(later.label)
    refs_moved = tuple(earlier.legal_refs) != tuple(later.legal_refs)
    if label_moved and refs_moved:
        return "label_and_legal_refs_evolved"
    if label_moved:
        return "label_evolved"
    if refs_moved:
        return "legal_refs_evolved"
    return "unchanged"


def _merge_source_refs(*occurrences: AeipOccurrence | None) -> tuple[str, ...]:
    """Return validated occurrence source ids in stable, duplicate-free order."""
    refs: list[str] = []
    for occurrence in occurrences:
        if occurrence is None:
            continue
        for ref in occurrence.source_refs:
            clean = str(ref).strip()
            if clean and clean not in refs:
                refs.append(clean)
    return tuple(refs)


def plan_chains(
    inventory: AeipInventory,
    *,
    adjudications: AdjudicationSet | None = None,
) -> ChainPlan:
    """Plan the chain stamps and evolution records for the family.

    Only programmes spanning more than one revision get a chain: a single-year
    programme has no cross-revision identity to assert. The plan is emitted
    only for events free of blocking ambiguity, so a partially-adjudicated
    corpus yields a partial plan rather than a guessed one.
    """
    resolved = adjudications or AdjudicationSet.empty()
    ambiguities = _detect_ambiguities(inventory, resolved)
    blocked = {slug for ambiguity in ambiguities for slug in ambiguity.slugs}
    order = {revision: index for index, revision in enumerate(inventory.revisions)}

    entries: list[ChainPlanEntry] = []
    singles: list[AeipEvent] = []
    for event in inventory.events:
        if event.slug in blocked:
            continue
        event_entries, event_singles = _plan_event(event, resolved, inventory.revisions, order)
        entries.extend(event_entries)
        singles.extend(event_singles)

    return ChainPlan(
        entries=tuple(entries),
        ambiguities=ambiguities,
        single_revision_events=tuple(singles),
    )


def _plan_event(
    event: AeipEvent,
    adjudications: AdjudicationSet,
    revisions: tuple[str, ...],
    order: dict[str, int],
) -> tuple[list[ChainPlanEntry], list[AeipEvent]]:
    if not event.spans_multiple_revisions:
        return [], [event]
    entries: list[ChainPlanEntry] = []
    singles: list[AeipEvent] = []
    for chain_id, rows in _segments_for(event, adjudications, order):
        if len(rows) < 2:
            singles.append(AeipEvent(slug=event.slug, title=event.title, occurrences=tuple(rows)))
            continue
        pairs = _adjacent_evolutions(chain_id, rows)
        pairs += _retirement_evolution(chain_id, rows, revisions, order)
        entries.append(ChainPlanEntry(chain_id=chain_id, title=event.title, occurrences=tuple(rows), pairs=pairs))
    return entries, singles


def _adjacent_evolutions(chain_id: str, rows: list[AeipOccurrence]) -> tuple[EvolutionPair, ...]:
    return tuple(
        EvolutionPair(
            chain_id=chain_id,
            from_revision=earlier.revision_id,
            to_revision=later.revision_id,
            evolution_kind=_classify_pair(earlier, later),
            legal_refs=later.legal_refs,
            source_refs=_merge_source_refs(earlier, later),
        )
        for earlier, later in pairwise(rows)
    )


def _retirement_evolution(
    chain_id: str,
    rows: list[AeipOccurrence],
    revisions: tuple[str, ...],
    order: dict[str, int],
) -> tuple[EvolutionPair, ...]:
    last_index = order[rows[-1].revision_id]
    if last_index >= len(revisions) - 1:
        return ()
    last = rows[-1]
    return (
        EvolutionPair(
            chain_id=chain_id,
            from_revision=last.revision_id,
            to_revision=revisions[last_index + 1],
            evolution_kind="retired",
            legal_refs=last.legal_refs,
            source_refs=_merge_source_refs(last),
        ),
    )


def render_evolution_record(
    pair: EvolutionPair,
    *,
    casilla_id: str,
    modelo_id: str = "100",
    legal_refs: tuple[str, ...] | None = None,
    source_refs: tuple[str, ...] | None = None,
) -> str:
    """Render one evolution record fragment for review or a prepared write.

    ``legal_refs`` defaults to the refs the pair carries at its target
    revision. ``source_refs`` defaults to the validated refs carried by the
    pair; an explicit value remains available for review-only rendering.
    """
    refs = ", ".join(f'"{ref}"' for ref in (pair.legal_refs if legal_refs is None else legal_refs))
    sources = ", ".join(f'"{ref}"' for ref in (pair.source_refs if source_refs is None else source_refs))
    record_id = f"{modelo_id}-{casilla_id}-{pair.from_revision}-{pair.to_revision}-{pair.evolution_kind}"
    return "\n".join(
        (
            f'[[revisions."{pair.to_revision}".casilla_continuidad_evolutions]]',
            f'id = "m{record_id}"',
            f'continuidad_id = "{pair.chain_id}"',
            f'from_revision = "{pair.from_revision}"',
            f'to_revision = "{pair.to_revision}"',
            f'evolution_kind = "{pair.evolution_kind}"',
            f"legal_refs = [{refs}]",
            f"source_refs = [{sources}]",
        ),
    )
