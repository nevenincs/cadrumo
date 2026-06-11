---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-06-10'
step_id: 'S18'
related:
  - "[[2026-06-10-docs-terminology-search-plan]]"
---




# Implement the wrangling corrections layer as tested code: casilla-revision dedupe, locale-quadruplet collapse, score-floor and TOC-noise filtering, directory-cluster reading (ADR D6)

## Scope

- `dev docs terminology compiler tests`

## Description

Implements ADR **D6** "output wrangling is a typed transformation layer, not
ad-hoc filtering": the four documented raw-hit corrections as TESTED CODE with
an audit trail. New module `dev/docs/terminology/_wrangle.py` consumes the
resolver's `ResolutionResult` (the `tuple[ResolvedTarget, ...]` each carrying
`record` = unified SearchRecord + `source_hit` = raw score) and produces a
`WrangledResult` the term-to-target mapping consumes.

The single entry point is `wrangle(resolution, *, score_floor=STRONG_SIGNAL_SCORE_FLOOR)
-> WrangledResult`. Composition order (documented, deterministic):

1. **score-floor + TOC-noise filtering** -- drop a target whose `source_hit`
   score is strictly below the floor (the `STRONG_SIGNAL_SCORE_FLOOR = 0.5`
   named constant, the research's ~0.5 strong-signal convention; also a
   `wrangle` parameter, never a magic literal), and drop low-value navigation /
   table-of-contents pages (a `page:` record whose final path segment is
   `index` / `toctree` / `contents` / `genindex` / `search`). Each drop extends
   the resolver's `DroppedHit` trail with a reason.
2. **casilla-revision dedupe** -- collapse multiple hits landing on the SAME
   casilla record id (`casilla:<modelo>:<number>:<segmento>`) to one, keeping
   the highest-scored hit; the merged hits are recorded as `CollapsedHit` rows
   with `CASILLA_REVISION_DUPLICATE`.
3. **locale-quadruplet collapse** -- collapse the documented 4x locale crowding:
   remaining same-record-id near-duplicates (the parallel es/en/ca/hu source
   files produce four hits per concept) collapse to the best-scored one, with
   `LOCALE_QUADRUPLET_DUPLICATE` collapse rows.
4. **directory-cluster reading** -- `read_clusters` groups the surviving targets
   by `(surface, locator)` where the locator is the modelo (casilla), the
   domain (concept), or the top path segment otherwise; returns
   `DirectoryCluster`s sorted dominant-first (by size, then max score) so a
   consumer can boost or tie-break on the dominant cluster deterministically.

## Outcome

Landed (one atomic commit, see Notes for hash). 12 new real-behaviour tests;
full subtree 62 passed (S15 12 + S16 14 + S17 24 + S18 12). ruff / ruff format /
ty clean; collect-only clean.

**`WrangledResult` shape** (strict frozen dataclass): `targets:
tuple[ResolvedTarget, ...]` (cleaned, deduped, floor-filtered, sorted by
descending `ranking_weight` then `id`), `dropped: tuple[DroppedHit, ...]` (the
resolver's drops carried forward verbatim PLUS the filter drops), `collapsed:
tuple[CollapsedHit, ...]` (every dedupe/collapse merge, naming `into_record_id`
+ `reason`), `clusters: tuple[DirectoryCluster, ...]` (dominant-first). Helper
properties `target_count` / `dropped_count` / `collapsed_count`.

**New typed records:** `DirectoryCluster` (strict frozen pydantic: surface,
locator, size, max_score, record_ids), `CollapsedHit` (frozen dataclass: merged
target, into_record_id, reason), `CollapseReason` StrEnum.

**Score-floor constant:** `STRONG_SIGNAL_SCORE_FLOOR = 0.5`, exported, and the
default of the `score_floor` parameter -- proven configurable
(`test_score_floor_is_a_named_parameter_not_a_magic_literal`: floor 0.6 drops a
0.55 hit that floor 0.5 keeps).

**Extended audit trail:** nothing is silently discarded. A filter drop reuses
the resolver's `DropReason` enum (`UNKNOWN_PATH` for below-floor with the score
in the detail; `EXCLUDED_SURFACE` for TOC noise) so the wrangled drop trail is
one homogeneous report with the resolution-time drops; the resolver's
pre-existing drop is carried forward (asserted: `prior_drop in result.dropped`).
A dedupe/collapse merge is a `CollapsedHit` row naming the surviving record id.

Test names (`test_wrangle.py`, 12): `test_below_floor_hit_is_dropped_and_reported`
(ANTI-TAUTOLOGY), `test_score_floor_is_a_named_parameter_not_a_magic_literal`,
`test_toc_noise_page_is_dropped`, `test_content_page_is_not_dropped_as_toc_noise`,
`test_casilla_revision_collision_collapses_to_one_keeping_best_score`,
`test_distinct_casillas_are_not_collapsed`,
`test_locale_quadruplet_collapses_to_one` (ANTI-TAUTOLOGY: exactly 1 survivor +
3 collapse rows), `test_directory_cluster_reading_finds_the_dominant_cluster`,
`test_read_clusters_is_deterministic_and_total`,
`test_wrangle_composes_all_corrections_and_extends_the_audit_trail` (end-to-end:
all four fire + resolver drop carried forward),
`test_targets_are_sorted_by_descending_weight_then_id`,
`test_empty_resolution_wrangles_to_empty`. Tests build realistic
`ResolvedTarget`s from REAL records (real M303 casilla projection, real prorrata
concept card) plus the deliberate edge cases (cross-revision casilla collision,
4-locale quadruplet, below-floor hit, TOC page, directory cluster) -- no mocks.

## Notes

- **No PM tokens in production code** (ADR ids only); cross-step references in
  the module/test docstrings are phrased by function ("the resolver", "the
  sweep") rather than step ids, per `aeat-source-hygiene`.
- **`__init__.py`** now re-exports the wrangling surface (`wrangle`,
  `WrangledResult`, `read_clusters`, `DirectoryCluster`, `CollapsedHit`,
  `CollapseReason`, `STRONG_SIGNAL_SCORE_FLOOR`) alongside the S15/S16/S17
  surfaces. This completes W03.P08.
- **S19 handoff (the sweep):** the sweep enumerates the query vocabulary from
  the Handbook concepts (preferred/admitted terms, four-language translations,
  hidden search forms), runs each through the resident RAG service to get raw
  chunk hits, maps them through the resolver
  (`resolve_chunk_hits(hits) -> ResolutionResult`), then wrangles:
  **`wrangle(resolution_result) -> WrangledResult`** (optionally passing
  `score_floor=` to tune the strong-signal cut). The sweep reads
  `WrangledResult.targets` as the per-term ranked term-to-target relevance
  mapping (each `ResolvedTarget.record.target` is the deep link, its
  `ranking_weight` the rank), `WrangledResult.clusters` as the dominant-cluster
  signal when scores are thin, and `WrangledResult.dropped` /
  `.collapsed` as the audit of what was filtered. The laundering rule (ship
  rankings + identifiers only, no SPLADE vectors) applies at the sweep's
  serialisation boundary, not here -- the wrangled targets already carry only
  ids, targets, and normalised weights. aed5b6d7 (RAG expert) runs the sweep.

