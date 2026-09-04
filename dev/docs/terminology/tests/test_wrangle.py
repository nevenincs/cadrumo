"""Real-behaviour conformance for the wrangling corrections layer.

The raw-hit corrections are required to be TESTED CODE, not ad-hoc
filtering. :func:`~dev.docs.terminology._wrangle.wrangle` takes the resolver's
:class:`~dev.docs.terminology._resolution.ResolutionResult` and applies the four
documented corrections -- score-floor + TOC-noise filtering, casilla-revision
dedupe, locale-quadruplet collapse, directory-cluster reading -- emitting the
wrangled set the sweep consumes plus an extended drop / collapse / cluster
audit.

The tests construct realistic :class:`ResolvedTarget` sets from REAL projected
records (real casilla records via the registry projection, real concept cards)
plus the deliberate edge cases the corrections exist to fix: a cross-revision
casilla collision, a four-locale quadruplet, a below-floor hit, a TOC-noise
page, and a directory cluster. Anti-tautology gates assert a below-floor hit is
actually dropped+reported and a quadruplet actually collapses to one.
"""

from __future__ import annotations

import pytest

from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.modelo import Modelo

from .._resolution import (
    ChunkHit,
    DroppedHit,
    DropReason,
    GroundingSurface,
    ResolutionResult,
    ResolvedTarget,
)
from .._wrangle import (
    STRONG_SIGNAL_SCORE_FLOOR,
    CollapseReason,
    DirectoryCluster,
    WrangledResult,
    read_clusters,
    wrangle,
)
from ..search_record import SearchRecordKind
from ..unified_record import (
    RankingTier,
    SearchRecord,
    SearchRecordMetadata,
    to_search_record,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


# ---------------------------------------------------------------------------
# Builders — realistic ResolvedTargets from real records + constructed hits
# ---------------------------------------------------------------------------


def _hit(path: str, score: float) -> ChunkHit:
    return ChunkHit(path=path, line_start=1, line_end=20, score=score)


def _real_casilla_target(score: float, *, index: int = 0) -> ResolvedTarget:
    """A ResolvedTarget built from a REAL M303 casilla projection record."""
    from ..casilla_projection import project_modelo_casillas

    records = project_modelo_casillas(Modelo.M303)
    unified = to_search_record(records[index])
    path = f"src/cadrumo/_data/registry/aeat/modelos/303/revisions/2022/casillas/{index:04d}-casillas.part-001.toml"
    return ResolvedTarget(surface=GroundingSurface.CASILLA, record=unified, source_hit=_hit(path, score))


def _real_concept_target(score: float) -> ResolvedTarget:
    """A ResolvedTarget built from the REAL prorrata concept card."""
    from .._concept_cards import project_concept_cards

    cards, _ = project_concept_cards()
    prorrata = next(c for c in cards if c.concept_id == "prorrata")
    unified = to_search_record(prorrata)
    return ResolvedTarget(
        surface=GroundingSurface.CASILLA,  # concept hits arrive via various sources
        record=unified,
        source_hit=_hit("src/cadrumo/_data/terminology/concepts/prorrata.toml", score),
    )


def _page_target(rel: str, score: float, *, surface: GroundingSurface = GroundingSurface.DOCS) -> ResolvedTarget:
    record = SearchRecord(
        id=f"page:{rel}",
        kind=SearchRecordKind.PAGE,
        tier=RankingTier.FULLTEXT,
        title=rel,
        descriptions={OutputLanguage.ES: "documentation"},
        target=f"{rel}.html",
        ranking_weight=0.5,
        metadata=SearchRecordMetadata(),
    )
    return ResolvedTarget(surface=surface, record=record, source_hit=_hit(f"docs/{rel}.md", score))


# ---------------------------------------------------------------------------
# Correction 1 — score-floor + TOC-noise filtering (anti-tautology)
# ---------------------------------------------------------------------------


def test_below_floor_hit_is_dropped_and_reported() -> None:
    """Anti-tautology: a hit below the score floor is actually dropped+reported.

    A target whose source hit scored below ``STRONG_SIGNAL_SCORE_FLOOR`` must
    NOT survive wrangling and MUST appear in the drop trail with a reason --
    never silently kept.
    """
    strong = _page_target("how-to/setup", 0.9)
    weak = _page_target("how-to/weak", STRONG_SIGNAL_SCORE_FLOOR - 0.2)
    result = wrangle(ResolutionResult(resolved=(strong, weak)))

    surviving_ids = {target.record.id for target in result.targets}
    assert "page:how-to/setup" in surviving_ids
    assert "page:how-to/weak" not in surviving_ids, "below-floor hit was not dropped"
    weak_drops = [d for d in result.dropped if d.hit.path == "docs/how-to/weak.md"]
    assert weak_drops, "below-floor drop was not reported"
    assert "below strong-signal score floor" in weak_drops[0].detail


def test_score_floor_is_a_named_parameter_not_a_magic_literal() -> None:
    """The score floor is configurable: a stricter floor drops more hits."""
    mid = _page_target("how-to/mid", 0.55)
    lenient = wrangle(ResolutionResult(resolved=(mid,)), score_floor=0.5)
    strict = wrangle(ResolutionResult(resolved=(mid,)), score_floor=0.6)
    assert lenient.target_count == 1
    assert strict.target_count == 0
    assert strict.dropped_count == 1


def test_toc_noise_page_is_dropped() -> None:
    """A navigation / table-of-contents page is dropped as low-value noise.

    Even a high-scored ``index`` page is TOC noise: it is a landing page, not a
    content match, so it is filtered with a reason.
    """
    content = _page_target("how-to/profile-setup", 0.8)
    toc = _page_target("how-to/index", 0.95)  # high score but a nav page
    result = wrangle(ResolutionResult(resolved=(content, toc)))

    surviving_ids = {target.record.id for target in result.targets}
    assert "page:how-to/profile-setup" in surviving_ids
    assert "page:how-to/index" not in surviving_ids
    toc_drops = [d for d in result.dropped if "table-of-contents" in d.detail]
    assert toc_drops


def test_content_page_is_not_dropped_as_toc_noise() -> None:
    """A real content page (non-index stem) survives the TOC filter."""
    content = _page_target("explanation/iva-regime", 0.7)
    result = wrangle(ResolutionResult(resolved=(content,)))
    assert result.target_count == 1


# ---------------------------------------------------------------------------
# Correction 2 — casilla-revision dedupe
# ---------------------------------------------------------------------------


def test_casilla_revision_collision_collapses_to_one_keeping_best_score() -> None:
    """Two hits on the SAME casilla id collapse to one, keeping the higher score.

    Built from a real M303 casilla record: two hits (different scores) on the
    same casilla collapse, the higher-scored survives, and the collapse is
    recorded with the casilla-revision reason.
    """
    high = _real_casilla_target(0.85, index=0)
    low = _real_casilla_target(0.6, index=0)  # same record id, lower score
    result = wrangle(ResolutionResult(resolved=(high, low)))

    casilla_ids = [t.record.id for t in result.targets if t.record.kind is SearchRecordKind.CASILLA]
    assert len(casilla_ids) == len(set(casilla_ids)), "duplicate casilla id survived"
    assert len(casilla_ids) == 1
    survivor = next(t for t in result.targets if t.record.kind is SearchRecordKind.CASILLA)
    assert survivor.source_hit.score == 0.85  # the higher-scored hit won
    collapses = [c for c in result.collapsed if c.reason is CollapseReason.CASILLA_REVISION_DUPLICATE]
    assert len(collapses) == 1
    assert collapses[0].merged.source_hit.score == 0.6


def test_distinct_casillas_are_not_collapsed() -> None:
    """Distinct casilla ids are preserved (only same-id collisions collapse)."""
    a = _real_casilla_target(0.8, index=0)
    b = _real_casilla_target(0.8, index=1)
    result = wrangle(ResolutionResult(resolved=(a, b)))
    casilla_ids = {t.record.id for t in result.targets if t.record.kind is SearchRecordKind.CASILLA}
    assert len(casilla_ids) == 2


# ---------------------------------------------------------------------------
# Correction 3 — locale-quadruplet collapse (anti-tautology)
# ---------------------------------------------------------------------------


def test_locale_quadruplet_collapses_to_one() -> None:
    """Anti-tautology: four near-identical same-id hits collapse to exactly one.

    The research's documented 4x locale crowding: the parallel es/en/ca/hu
    source files produce four hits that resolve to one record id. They MUST
    collapse to one surviving target, keeping the best score, with three
    collapse rows recorded.
    """
    quad = (
        _page_target("how-to/setup", 0.9),
        _page_target("how-to/setup", 0.85),
        _page_target("how-to/setup", 0.7),
        _page_target("how-to/setup", 0.6),
    )
    result = wrangle(ResolutionResult(resolved=quad))

    setup_targets = [t for t in result.targets if t.record.id == "page:how-to/setup"]
    assert len(setup_targets) == 1, "locale quadruplet did not collapse to one"
    assert setup_targets[0].source_hit.score == 0.9  # best score survived
    locale_collapses = [c for c in result.collapsed if c.reason is CollapseReason.LOCALE_QUADRUPLET_DUPLICATE]
    assert len(locale_collapses) == 3
    for collapse in locale_collapses:
        assert collapse.into_record_id == "page:how-to/setup"


# ---------------------------------------------------------------------------
# Correction 4 — directory-cluster reading
# ---------------------------------------------------------------------------


def test_directory_cluster_reading_finds_the_dominant_cluster() -> None:
    """The dominant surface/modelo cluster across several hits is reported first.

    A cluster of three M303 casilla hits dominates a lone page hit; the
    clusters are returned dominant-first, so the M303 cluster leads.
    """
    targets = (
        _real_casilla_target(0.8, index=0),
        _real_casilla_target(0.75, index=1),
        _real_casilla_target(0.7, index=2),
        _page_target("how-to/setup", 0.9),
    )
    result = wrangle(ResolutionResult(resolved=targets))

    assert result.clusters, "no clusters read"
    dominant = result.clusters[0]
    assert isinstance(dominant, DirectoryCluster)
    assert dominant.surface == GroundingSurface.CASILLA.value
    assert dominant.locator == "modelo:303"
    assert dominant.size == 3
    assert dominant.max_score == pytest.approx(0.8)


def test_read_clusters_is_deterministic_and_total() -> None:
    """Every target lands in exactly one cluster; the result is order-stable."""
    targets = (
        _real_casilla_target(0.8, index=0),
        _real_casilla_target(0.75, index=1),
        _page_target("how-to/setup", 0.9),
        _page_target("explanation/x", 0.85),
    )
    clusters = read_clusters(targets)
    total_members = sum(cluster.size for cluster in clusters)
    assert total_members == len(targets)
    # Re-running yields an identical clustering (deterministic).
    assert read_clusters(targets) == clusters


# ---------------------------------------------------------------------------
# Composition + audit trail
# ---------------------------------------------------------------------------


def test_wrangle_composes_all_corrections_and_extends_the_audit_trail() -> None:
    """End-to-end: all four corrections fire and the resolver drop trail carries forward.

    Mixes a casilla collision, a locale quadruplet, a below-floor hit, a TOC
    page, and a pre-existing resolution-time drop. The result carries the
    cleaned targets, the extended drop trail (resolver drop + the two filter
    drops), and the collapse audit (casilla + locale).
    """
    prior_drop = DroppedHit(
        hit=_hit("totally/unmapped.bin", 0.1),
        reason=DropReason.UNKNOWN_PATH,
        detail="no resolution rule",
    )
    resolved = (
        _real_casilla_target(0.85, index=0),
        _real_casilla_target(0.6, index=0),  # casilla dupe
        _page_target("how-to/setup", 0.9),
        _page_target("how-to/setup", 0.7),  # locale dupe
        _page_target("how-to/weak", 0.2),  # below floor
        _page_target("how-to/index", 0.95),  # TOC noise
    )
    result = wrangle(ResolutionResult(resolved=resolved, dropped=(prior_drop,)))

    assert isinstance(result, WrangledResult)
    surviving_ids = {t.record.id for t in result.targets}
    expected_casilla_id = resolved[0].record.id
    assert surviving_ids == {expected_casilla_id, "page:how-to/setup"}
    # Casilla dupe + locale dupe both collapsed.
    assert result.collapsed_count == 2
    reasons = {c.reason for c in result.collapsed}
    assert reasons == {CollapseReason.CASILLA_REVISION_DUPLICATE, CollapseReason.LOCALE_QUADRUPLET_DUPLICATE}
    # The resolver drop is carried forward, plus the below-floor and TOC drops.
    assert prior_drop in result.dropped
    assert result.dropped_count == 3


def test_targets_are_sorted_by_descending_weight_then_id() -> None:
    """The surviving targets are deterministically ordered for a stable index."""
    targets = (
        _real_casilla_target(0.8, index=1),
        _real_concept_target(0.9),  # concept weight 1.0 outranks casilla 0.7
    )
    result = wrangle(ResolutionResult(resolved=targets))
    weights = [t.record.ranking_weight for t in result.targets]
    assert weights == sorted(weights, reverse=True)
    # The concept (weight 1.0) ranks first.
    assert result.targets[0].record.kind is SearchRecordKind.CONCEPT


def test_empty_resolution_wrangles_to_empty() -> None:
    """An empty resolution wrangles to an empty result (no crash, no clusters)."""
    result = wrangle(ResolutionResult(resolved=()))
    assert result.target_count == 0
    assert result.collapsed_count == 0
    assert result.clusters == ()
