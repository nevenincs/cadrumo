"""Wrangling corrections over the resolved sweep hits.

Output wrangling is a typed transformation layer, not
ad-hoc filtering: the raw-hit corrections are TESTED
CODE with an audit trail, not inline ``if score > 0.5`` scattered through the
compiler. This module takes the :class:`~dev.docs.terminology._resolution.ResolutionResult`
the chunk-to-target resolver produces and applies the four documented
corrections, emitting a :class:`WrangledResult` the sweep (the term-to-target
relevance mapping) consumes.

The four corrections, in composition order:

1. **score-floor + TOC-noise filtering** -- drop a resolved target whose
   originating hit scored below the strong-signal floor
   (:data:`STRONG_SIGNAL_SCORE_FLOOR`, the ~0.5 strong-signal convention), and
   drop low-value PAGE navigation / TOC / index records that pollute the tail.
   LEGAL records also use the full-text tier, but their ``LEGAL`` discriminator
   keeps them out of this PAGE-only filter.
2. **casilla-revision dedupe** -- collapse multiple hits landing on the SAME
   opaque casilla search-record id to one target, keeping the highest-scored
   hit. The canonical casilla identity remains typed metadata on the record,
   not a parseable id token.
3. **locale-quadruplet collapse** -- collapse the research's documented 4x
   locale crowding: several near-identical hits resolving to the same record
   ``id`` collapse to one, keeping the best score.
4. **directory-cluster reading** -- when scores collapse, the dominant cluster
   (by surface + modelo / domain) across several hits is the real signal;
   :func:`read_clusters` reports the clusters so a tie can be broken or a
   cluster boosted.

Every correction that REMOVES or MERGES a hit records why: filter drops extend
the resolver's :class:`~dev.docs.terminology._resolution.DroppedHit` trail, and
dedupe/collapse merges are recorded as :class:`CollapsedHit` rows naming the
surviving record id. Nothing is silently discarded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from ._resolution import DroppedHit, DropReason, ResolutionResult, ResolvedTarget
from .search_record import SearchRecordKind
from .unified_record import RankingTier

__all__ = [
    "STRONG_SIGNAL_SCORE_FLOOR",
    "CollapseReason",
    "CollapsedHit",
    "DirectoryCluster",
    "WrangledResult",
    "read_clusters",
    "wrangle",
]

#: The strong-signal relevance floor (the research's ~0.5 convention, the same
#: threshold the retrieval-verification step used). A resolved target whose
#: originating hit scored below this is dropped as noise: below ~0.5 the hybrid
#: index's signal is dominated by the low-score tail. Exposed as a named
#: constant (and a ``wrangle`` parameter) so it is never a magic literal.
STRONG_SIGNAL_SCORE_FLOOR = 0.5

#: Page record ids whose final path segment is one of these is treated as a
#: navigation / table-of-contents page (low search value): a hit on an index or
#: toctree landing page is TOC noise, not a content match.
_TOC_NOISE_PAGE_STEMS: frozenset[str] = frozenset({"index", "toctree", "contents", "genindex", "search"})


class CollapseReason(StrEnum):
    """Why two resolved hits were merged into one (the dedupe/collapse audit)."""

    #: Multiple hits landed on the same casilla record id.
    CASILLA_REVISION_DUPLICATE = "casilla_revision_duplicate"
    #: Multiple near-identical (locale-quadruplet) hits resolved to one record id.
    LOCALE_QUADRUPLET_DUPLICATE = "locale_quadruplet_duplicate"


#: Extra :class:`~dev.docs.terminology._resolution.DropReason` members the
#: filtering correction stamps. They reuse the resolver's enum so the wrangled
#: drop trail is one homogeneous report with the resolution-time drops.
_FILTER_DROP_DETAIL_BELOW_FLOOR = "below strong-signal score floor"
_FILTER_DROP_DETAIL_TOC_NOISE = "navigation / table-of-contents page (low search value)"


@dataclass(frozen=True, slots=True)
class CollapsedHit:
    """One resolved hit merged into a surviving target (dedupe / collapse audit).

    ``merged`` is the hit that was removed; ``into_record_id`` is the id of the
    surviving record it collapsed into; ``reason`` says which correction merged
    it. Nothing is silently dropped -- a collapsed hit is auditable.
    """

    merged: ResolvedTarget
    into_record_id: str
    reason: CollapseReason


class DirectoryCluster(BaseModel):
    """A dominant directory / surface cluster across the resolved hits.

    The "when scores collapse, read the dominant directory cluster
    across 3-5 hits" signal, materialised as typed data: a cluster groups
    resolved targets by their surface plus a coarse locator (modelo for
    casillas, domain for concepts, the top path segment otherwise). ``size`` is
    the member count and ``max_score`` the strongest member's hit score, so a
    consumer can boost or tie-break on the dominant cluster deterministically.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    surface: str = Field(min_length=1, max_length=32)
    locator: str = Field(min_length=1, max_length=240)
    size: int = Field(ge=1)
    max_score: float = Field(ge=0.0, le=1.0)
    #: The record ids in this cluster, sorted for determinism.
    record_ids: tuple[str, ...] = Field(min_length=1)


@dataclass(frozen=True, slots=True)
class WrangledResult:
    """The wrangled sweep result the term-to-target mapping consumes.

    ``targets`` is the cleaned, deduplicated, floor-filtered set (sorted by
    descending ranking weight then id for determinism). ``dropped`` extends the
    resolver's drop trail with the filter drops; ``collapsed`` records every
    dedupe/collapse merge; ``clusters`` is the dominant-cluster reading over the
    surviving targets.
    """

    targets: tuple[ResolvedTarget, ...]
    dropped: tuple[DroppedHit, ...] = field(default=())
    collapsed: tuple[CollapsedHit, ...] = field(default=())
    clusters: tuple[DirectoryCluster, ...] = field(default=())

    @property
    def target_count(self) -> int:
        """How many targets survived wrangling."""
        return len(self.targets)

    @property
    def dropped_count(self) -> int:
        """How many hits were dropped (resolution-time plus filter drops)."""
        return len(self.dropped)

    @property
    def collapsed_count(self) -> int:
        """How many hits were merged by dedupe / locale collapse."""
        return len(self.collapsed)


def wrangle(
    resolution: ResolutionResult,
    *,
    score_floor: float = STRONG_SIGNAL_SCORE_FLOOR,
) -> WrangledResult:
    """Apply the four documented corrections to a resolution result.

    Composition order (documented, deterministic):

    1. score-floor + TOC-noise filtering (removes weak / navigation hits),
    2. casilla-revision dedupe (collapses same-casilla hits),
    3. locale-quadruplet collapse (collapses same-id near-duplicates),
    4. directory-cluster reading (reports the dominant clusters).

    Args:
        resolution: The resolver's resolution result (resolved targets + the
            resolution-time drop trail, carried forward verbatim).
        score_floor: The strong-signal floor; a target whose ``source_hit``
            score is strictly below it is dropped. Defaults to
            :data:`STRONG_SIGNAL_SCORE_FLOOR`.

    Returns:
        A :class:`WrangledResult` carrying the cleaned targets and the extended
        drop / collapse / cluster audit.
    """
    filtered, filter_drops = _filter_floor_and_toc(resolution.resolved, score_floor)
    deduped, casilla_collapses = _dedupe_casillas(filtered)
    collapsed_targets, locale_collapses = _collapse_locale_quadruplets(deduped)
    clusters = read_clusters(collapsed_targets)

    ordered = tuple(
        sorted(
            collapsed_targets,
            key=lambda target: (-target.record.ranking_weight, target.record.id),
        ),
    )
    return WrangledResult(
        targets=ordered,
        dropped=(*resolution.dropped, *filter_drops),
        collapsed=(*casilla_collapses, *locale_collapses),
        clusters=clusters,
    )


# ---------------------------------------------------------------------------
# Correction 1 — score-floor + TOC-noise filtering
# ---------------------------------------------------------------------------


def _filter_floor_and_toc(
    targets: tuple[ResolvedTarget, ...],
    score_floor: float,
) -> tuple[tuple[ResolvedTarget, ...], tuple[DroppedHit, ...]]:
    kept: list[ResolvedTarget] = []
    drops: list[DroppedHit] = []
    for target in targets:
        if target.source_hit.score < score_floor:
            drops.append(
                DroppedHit(
                    hit=target.source_hit,
                    reason=DropReason.UNKNOWN_PATH,
                    detail=f"{_FILTER_DROP_DETAIL_BELOW_FLOOR} ({target.source_hit.score:.3f} < {score_floor})",
                ),
            )
            continue
        if _is_toc_noise(target):
            drops.append(
                DroppedHit(
                    hit=target.source_hit,
                    reason=DropReason.EXCLUDED_SURFACE,
                    detail=f"{_FILTER_DROP_DETAIL_TOC_NOISE}: {target.record.id}",
                ),
            )
            continue
        kept.append(target)
    return tuple(kept), tuple(drops)


def _is_toc_noise(target: ResolvedTarget) -> bool:
    # Only full-text PAGE records can be TOC noise; a concept / casilla / CLI
    # navigation entry or LEGAL record is never filtered as TOC noise. The kind
    # discriminator, rather than the ranking tier alone, is authoritative here.
    if target.record.tier is not RankingTier.FULLTEXT:
        return False
    if target.record.kind is not SearchRecordKind.PAGE:
        return False
    # PAGE record ids use ``page:<rel>`` for built docs and ``code:<dotted>``
    # for API targets. A LEGAL record may use ``legal:<id>``, but it has already
    # returned above because its discriminator is LEGAL, not PAGE.
    record_id = target.record.id
    if not record_id.startswith("page:"):
        return False
    rel = record_id[len("page:") :]
    final_segment = rel.rsplit("/", 1)[-1].lower()
    return final_segment in _TOC_NOISE_PAGE_STEMS


# ---------------------------------------------------------------------------
# Correction 2 — casilla-revision dedupe
# ---------------------------------------------------------------------------


def _dedupe_casillas(
    targets: tuple[ResolvedTarget, ...],
) -> tuple[tuple[ResolvedTarget, ...], tuple[CollapsedHit, ...]]:
    # Group casilla targets by record id; keep the highest-scored hit, record
    # the rest as collapsed. Non-casilla targets pass through untouched (their
    # same-id collapse is the locale step's concern).
    best_by_id: dict[str, ResolvedTarget] = {}
    collapses: list[CollapsedHit] = []
    passthrough: list[ResolvedTarget] = []
    order: list[str] = []
    for target in targets:
        if target.record.kind is not SearchRecordKind.CASILLA:
            passthrough.append(target)
            continue
        record_id = target.record.id
        incumbent = best_by_id.get(record_id)
        if incumbent is None:
            best_by_id[record_id] = target
            order.append(record_id)
            continue
        winner, loser = _higher_scored(incumbent, target)
        best_by_id[record_id] = winner
        collapses.append(
            CollapsedHit(merged=loser, into_record_id=record_id, reason=CollapseReason.CASILLA_REVISION_DUPLICATE),
        )
    survivors = [best_by_id[record_id] for record_id in order]
    return tuple((*passthrough, *survivors)), tuple(collapses)


# ---------------------------------------------------------------------------
# Correction 3 — locale-quadruplet collapse
# ---------------------------------------------------------------------------


def _collapse_locale_quadruplets(
    targets: tuple[ResolvedTarget, ...],
) -> tuple[tuple[ResolvedTarget, ...], tuple[CollapsedHit, ...]]:
    # Any remaining same-record-id duplicates (the locale-quadruplet crowding:
    # the parallel es/en/ca/hu source files produce four near-identical hits
    # that resolve to one record) collapse to the highest-scored hit.
    best_by_id: dict[str, ResolvedTarget] = {}
    collapses: list[CollapsedHit] = []
    order: list[str] = []
    for target in targets:
        record_id = target.record.id
        incumbent = best_by_id.get(record_id)
        if incumbent is None:
            best_by_id[record_id] = target
            order.append(record_id)
            continue
        winner, loser = _higher_scored(incumbent, target)
        best_by_id[record_id] = winner
        collapses.append(
            CollapsedHit(merged=loser, into_record_id=record_id, reason=CollapseReason.LOCALE_QUADRUPLET_DUPLICATE),
        )
    survivors = tuple(best_by_id[record_id] for record_id in order)
    return survivors, tuple(collapses)


# ---------------------------------------------------------------------------
# Correction 4 — directory-cluster reading
# ---------------------------------------------------------------------------


def read_clusters(targets: tuple[ResolvedTarget, ...]) -> tuple[DirectoryCluster, ...]:
    """Group resolved targets into dominant surface / directory clusters.

    The research's "read the dominant cluster across 3-5 hits when the score
    signal is thin" reading, as a deterministic transformation: targets are
    grouped by ``(surface, locator)`` where the locator is the modelo (casilla),
    the domain (concept), or the top path segment of the source hit (otherwise).
    Clusters are returned sorted by descending size then descending max score
    then key, so the dominant cluster is first.

    Args:
        targets: The resolved (and already deduped) targets.

    Returns:
        The clusters, dominant first.
    """
    grouped: dict[tuple[str, str], list[ResolvedTarget]] = {}
    for target in targets:
        key = (target.surface.value, _cluster_locator(target))
        grouped.setdefault(key, []).append(target)

    clusters: list[DirectoryCluster] = []
    for (surface, locator), members in grouped.items():
        clusters.append(
            DirectoryCluster(
                surface=surface,
                locator=locator,
                size=len(members),
                max_score=max(member.source_hit.score for member in members),
                record_ids=tuple(sorted(member.record.id for member in members)),
            ),
        )
    clusters.sort(key=lambda cluster: (-cluster.size, -cluster.max_score, cluster.surface, cluster.locator))
    return tuple(clusters)


def _cluster_locator(target: ResolvedTarget) -> str:
    metadata = target.record.metadata
    if metadata.modelo:
        return f"modelo:{metadata.modelo}"
    if metadata.domain:
        return f"domain:{metadata.domain}"
    # Fall back to the top directory segment of the originating hit path.
    parts = target.source_hit.posix_path.parts
    if len(parts) >= 2:
        return "/".join(parts[:2])
    return parts[0] if parts else target.record.id


def _higher_scored(left: ResolvedTarget, right: ResolvedTarget) -> tuple[ResolvedTarget, ResolvedTarget]:
    """Return ``(winner, loser)`` by hit score, with record id as a stable tiebreak."""
    if right.source_hit.score > left.source_hit.score:
        return right, left
    if right.source_hit.score < left.source_hit.score:
        return left, right
    # Equal scores: keep the lexicographically smaller record id for determinism.
    if right.record.id < left.record.id:
        return right, left
    return left, right
