---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-06-10'
step_id: 'S19'
related:
  - "[[2026-06-10-docs-terminology-search-plan]]"
---




# Implement the query-vocabulary sweep runner: every enrolled concept's terms, translations, and hidden forms swept through the resident RAG service (port 8766, timeout 30, reindex-before-sweep per W01.P03) into ranked term-to-target relevance mappings, with a cadence re-run verb whose diffs are reviewed like any generated-but-committed surface (ADR D6)

## Scope

- `dev docs sweep runner`

## Description

Implements ADR **D6** -- the query-vocabulary sweep, the RAG-as-build-oracle:
a CLOSED query vocabulary makes runtime RAG unnecessary, so the retrieval runs
ONCE here on the dev box and ships as plain ranked data, making the offline
palette "semantic" without shipping a model. New modules under
`dev/docs/terminology/`: `_sweep.py` (the runner + typed mapping), `_sweep_cli.py`
+ `sweep.py` (the cadence verb), plus a real-captured fixture.

The runner composes the pipeline already built: enumerate vocabulary -> reindex
-before-sweep -> per query (RAG retrieval -> `resolve_chunk_hits` ->
`wrangle`) -> a laundered term-to-target relevance mapping. Also added a
CONCEPT grounding surface + a `src/aeat/_data/terminology/concepts/*.toml`
resolution rule to the resolver (a sweep hit on a concept fragment resolves to
its card -- a genuine need the sweep surfaced; additive, existing resolution
tests stay green).

## Outcome

Landed (one atomic commit, see Notes for hash). 8 new sweep unit tests + 1
live-service integration test; full subtree 70 unit passed (62 prior + 8 sweep).
ruff / ruff format / ty clean; collect-only clean. The integration test ran
LIVE against the resident service and SKIPPED gracefully (the service was busy
behind a peer index-rebuild holding the single-writer lock -- the documented
degradation, not a failure).

**Vocabulary enumeration:** `enumerate_query_vocabulary(handbook, concept_ids=)`
emits one `SweepQuery` per distinct term label across all four language sections
(preferred + admitted) plus every hidden search form, deduped per concept,
keeping the concept_id + language association. **53 distinct query strings**
across the 95 concepts (concentrated in the 20 curated concepts; the 75
scaffold-empty drafts carry no terms yet). prorrata yields its 7 expected
queries (prorrata/regla de prorrata/prorrateo + hidden prorateo/pro rata/
deductible proportion/aranyositas).

**Relevance-mapping pydantic shape (proving laundering -- ids/targets/weights
only):**
- `TermTargetRef` (strict frozen): `record_id`, `target`, `kind`, `surface`,
  `ranking_weight` -- and NOTHING else. No vector, no SPLADE/sparse map, no raw
  score, no source path. The laundering test asserts the serialised JSON
  contains none of `vector`/`embedding`/`sparse`/`splade`/`"score"`/`"path"`/
  `"snippet"`, and that the target field set is exactly the five laundered
  fields.
- `TermRelevanceMapping` (strict frozen): `query`, `concept_id`, `language`,
  `targets: tuple[TermTargetRef]`, `dropped_count`, `collapsed_count` (audit
  COUNTS only -- per-hit detail stays in the build log), `dominant_cluster`
  (an identifier string, not a vector).
- `SweepResult` (strict frozen, JSON-serialisable): `mappings`, `query_count`,
  `concept_count`, `reindex_note`, `score_floor`. Round-trips through
  `model_dump_json` / `model_validate_json` (the landing-step seam).

**Reindex-before-sweep handling (+ service busy):** `_reindex_before_sweep`
calls the mandated `run_incremental_reindex` first, but the resident store is
single-writer and a long peer index-rebuild held the lock (jobs showed "queued
behind writer lock, ~2984s elapsed" / "embed+upsert 31488/57473, ~5137s
elapsed"). The runner does NOT hang on a queued rebuild: a `ReindexError` /
timeout downgrades to a note (`"reindex not confirmed (service busy/queued);
swept against current index"`) and the sweep proceeds against the current index
state (the sidecars are already indexed; the golden queries pass live). The
`run_sweep(reindex=False)` path skips it entirely for the recorded-client test.

**Real prorrata sweep result (the proof the concept works end to end):** a
live sweep of the 7 prorrata queries returned real targets deep-linking across
surfaces:
- `'prorrata'` -> the prorrata-especial concept card
  (`glossary.html#term-prorrata-especial`, w=0.86) + an M390 casilla
  (`search.html?q=390+662`); dominant cluster `casilla:modelo:390`.
- `'regla de prorrata'` -> the concept card (w=0.91) + the BOE IVA-law article
  (`boe.es/...BOE-A-1992-28740#a104`, the prorrata legal grounding); 4 collapsed
  (locale-quadruplet collapse fired); cluster `legal`.
- `'pro rata'` (en) -> two concept cards + a BOE legal target.
- `'deductible proportion'` (en) -> the prorrata concept card (w=0.99) + codebase
  API stubs.
- thin-signal terms (`aranyositas`/`prorateo`/`prorrateo`) -> 0 targets (below
  the 0.5 floor), honestly empty, not fabricated.
The committed fixture (`sweep-regla-de-prorrata.json`) is a REAL captured
service response (20 hits incl. `ley-37-1992-art-104.html.extracted.md` at
0.897); the deterministic test replays it through the real resolver+wrangler so
the BOE-art-104 + concept-card deep-links are proven on genuine data.

**Cadence re-run verb:** `python -m dev.docs.terminology.sweep run` (mirrors the
apidocs/preprocess dev-CLI precedent) -- options `--concept` (repeatable),
`--out PATH` (write the laundered mapping JSON), `--max-results`, `--score-floor`,
`--port`, `--timeout`, `--reindex/--no-reindex`. Regenerates the mapping; its
output diff is reviewed like any generated-but-committed surface.

Test names (`test_sweep.py`): `test_enumerate_vocabulary_covers_prorrata_terms_translations_and_hidden_forms`,
`test_enumerate_vocabulary_dedupes_identical_query_strings`,
`test_enumerate_full_vocabulary_is_a_bounded_closed_set`,
`test_real_sweep_maps_prorrata_to_its_grounding_targets` (END-TO-END on real
captured data), `test_sweep_mapping_is_laundered_ids_targets_weights_only`
(LAUNDERING), `test_sweep_result_is_json_serialisable_for_the_landing_step`,
`test_below_floor_query_yields_an_empty_but_recorded_mapping` (honest empty),
`test_live_service_sweep_runs_at_least_one_term` (INTEGRATION, live service,
skips when busy), `test_relevance_mapping_is_frozen`.

## Notes

- **No PM tokens in production code** (ADR ids only); cross-step references in
  docstrings are phrased by function ("the sibling landing step", "the
  resolver"), per `aeat-source-hygiene`.
- **`__init__.py`** re-exports the sweep surface; a CONCEPT grounding surface +
  concept-TOML rule were added to `_resolution.py` (additive).
- **Service-busy reality:** confirmed via `server jobs` -- a peer code reindex
  was mid-rebuild (~85 min elapsed), holding the single-writer lock; queries
  still served at a 60s timeout, but the explicit reindex queued. The runner is
  designed for exactly this (proceed against current index).
- **S20 handoff (landing step):** S20 serialises this runner's output to a
  committed relevance data file with ONE call --
  `SweepResult.model_dump_json(indent=2)` (the `--out` flag already does this) --
  and adds the gates: (a) every mapping's `concept_id` is an enrolled concept
  (cross-check against `load_terminology_handbook`), (b) every
  `TermTargetRef.target` resolves in the current build (the casilla/legal/
  concept/cli/docs anchors exist), (c) the laundering/licence gate (assert the
  committed file contains only ids/targets/weights -- no vector/sparse/SPLADE
  field, the same assertion `test_sweep_mapping_is_laundered_*` makes), (d) a
  drift gate (a stale mapping whose target no longer resolves fails loudly). The
  full sweep (all 53 queries, with the live reindex once the service settles) is
  S20's run-and-commit job; this step proved the runner on the bounded prorrata
  subset. S21 then mines synonym candidates from the sweep hits.

