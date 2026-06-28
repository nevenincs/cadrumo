---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-06-10'
modified: '2026-06-10'
step_id: 'S23'
related:
  - "[[2026-06-10-docs-terminology-search-plan]]"
---




# Inject the compiled record kinds via the Pagefind indexing API (addCustomRecord: concepts, casilla projections, CLI records) with typed metadata, filters, and ranking weights derived from the committed relevance data

## Scope

- `verify per-language index splits for es/en/ca/hu (ADR D5/D4)`
- `dev docs pagefind integration`

Implements ADR D4 + D5: the injection that puts the unified term-card /
casilla / CLI records into the Pagefind index via the seam built earlier in
this phase. Decoupled from the saturated RAG service and from the committed
relevance file - it works now on base weights and auto-upgrades when the
relevance file lands. Leaves the index well-formed for the palette query step.

## Description

- Ground the unified `SearchRecord` shape and the three deterministic
  projections (`project_concept_cards`, `project_casilla_search_records`,
  `project_cli_search_records`) plus the `to_search_record` funnel.
- Author `dev/docs/pagefind_inject.py`: `build_record_injector(repo_root) ->`
  the async callback for the post-build pass's `inject=` seam.
- Materialise every kind, funnel into unified records, and inject one Pagefind
  custom record per language section (so the es/en/ca/hu splits each receive
  the record) carrying the deep-link `url`, the searchable `content`, typed
  `meta` (kind/concept_id/domain/modelo/number/command_path), `filters`
  (kind/domain), and a `sort` ranking key from the base weight.
- Handle the CLI projection gracefully (skip-and-report on failure; concepts +
  casillas always land).
- Load the optional committed relevance file and boost matching records when
  present, base weights when absent.
- Prove the per-language splits and the relevance fallback with real
  Pagefind builds over real records (no mocks).
- Verify: ruff + format + ty clean, the inject tests green, S22's index test
  still green, collect-only clean.

## Outcome

### Injection callback design

`build_record_injector(repo_root, *, on_complete=None)` returns the async
callback the post-build pass invokes with the open `PagefindIndex` after the
HTML directory pass and before `write_files`. The callback materialises every
unified record, applies the relevance boost (when present), and injects each
record once per language section via `index.add_custom_record(url=record.target,
content=title+description, language=<lang>, meta=..., filters=..., sort=...)`.
The relevance map is read once at factory construction (re-read every build),
so a landed relevance file auto-applies. The factory accepts an `on_complete`
sink for the typed `InjectionStats` since the seam itself returns no value.

### Records injected per kind + the CLI-graceful handling

The full materialisation produces **7,116 unified records: 108 concepts +
5,962 deduped casillas + 210 CLI commands + 836 CLI options**. Injected once
per non-empty language section, that is ~28k custom records (concepts carry
four languages; casillas/CLI carry the languages their projection authored).
The CLI projection runs the live-command-tree subprocess walk; it is wrapped
so a transient CLI break is SKIPPED-AND-REPORTED (`cli_skipped_reason` on the
stats) rather than failing the whole injection - concepts and casillas, the
priority surfaces, always land. In this run the CLI projected cleanly (no
skip).

### Per-language split verification

Proven with real Pagefind builds: the concept-subset injection yields the
`es`/`en` splits (every concept's Spanish-invariant description forms the es
split; the pages form en), and a substantive-content test confirms ALL FOUR
`es`/`en`/`ca`/`hu` index splits form when records carry per-language text -
so the language routing is correct end to end. (A record whose `ca`/`hu`
description is short may not form a standalone fragment, which is a
content-length effect of Pagefind, not a routing defect; the routing test
isolates this.)

### Relevance boost (auto-upgrading) + base-weight fallback

`load_relevance_weights(repo_root)` reads
`src/aeat/_data/terminology/relevance/relevance.json` when present (the
sweep's committed output) and returns a `record-id -> weight` map, clamped to
`[0, 1]`; absent or unreadable yields an empty map. `_effective_weight` takes
the stronger of the base weight and the relevance weight (never lowering a
record below its tier base), so a sweep-favoured record ranks at least as
high as its base. Because the Pagefind index regenerates every build and the
relevance file is re-read each run, the boost applies AUTOMATICALLY the moment
the sweep lands the file - no re-injection. At the time of this step the file
is absent (the sweep is concurrent), so base weights stand; the loader and the
boost are tested both ways.

### Sample injected record (prorrata concept card)

`url = glossary.html#term-prorrata`; `content` = the title plus the
per-language description; `meta = {kind: concept, tier: term, title: prorrata,
weight: 1.000000, concept_id: prorrata, domain: concepto}`; `filters = {kind:
[concept], domain: [concepto]}`; `sort` = the descending-orderable weight key;
injected in es/en/ca/hu. The concept base weight is 1.0 (ADR-D5 tier one:
term cards first).

### Tests + pass

`dev/docs/tests/test_pagefind_inject.py` - 9 green (5 unit: record funnel,
meta/filters/sort payload, relevance boost-vs-base, relevance file
absent/present; 4 integration: per-language injection, four-language splits,
full-kind materialisation with graceful CLI, the injector-factory seam).
S22's `test_pagefind_index.py` stays 5 green (the seam is untouched).
`ruff check`, `ruff format --check`, `ty check`, collect-only all clean. The
full 7k-record Pagefind write is slow, so the suite proves the injection
mechanics on the concept subset and proves the full materialisation directly,
rather than repeating the slow write per test.

## Notes

- SCOPE FENCE honoured: S23 builds the INJECTION (records into the index).
  The Ctrl-K palette query + term-card rendering is the next step; the index
  is left well-formed for it.
- DECOUPLING confirmed: the injection needs neither the RAG service nor the
  committed relevance file. It works now on base weights and auto-upgrades on
  the relevance file landing, with no re-inject.
- I worked only in `dev/docs/` (my territory). I did not touch the concurrent
  sweep work in `dev/docs/terminology/` or the relevance file path - I only
  READ the relevance file's path (absent) via the loader.
- No PM wave/phase/step tokens in production code (ADR ids only here). Two ty
  suppressions on the test's dynamic `add_custom_record` / `_inject_records`
  calls are justified inline (the pagefind index object is dynamically typed).
- S24 handoff: the palette queries this index via Pagefind's JS search API
  (`pagefind.search(query)` -> results with `.data()` per result). The term
  card renders from the injected `meta` (kind, title, concept_id/domain for
  concepts, modelo/number for casillas, command_path for CLI) and jumps to the
  `url` (the deep link). The palette can narrow by the `kind`/`domain`
  `filters` and order by the `weight` `sort` key (ADR-D5 tiers: term cards
  first via the concept base weight, navigation second, full text third).
- Commit discipline: all verification ran first; staging and the commit are a
  single chained `git add ... ; git commit ...` over ONLY my explicit paths.

