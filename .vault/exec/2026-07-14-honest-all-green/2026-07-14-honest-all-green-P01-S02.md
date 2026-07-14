---
tags:
  - '#exec'
  - '#honest-all-green'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S02'
related:
  - "[[2026-07-14-honest-all-green-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace honest-all-green with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S02 and 2026-07-14-honest-all-green-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Fix the renta registry data or engine per the diagnosis with AEAT/BOE grounding and rerun the registry suite sequentially and ## Scope

- `registry renta surfaces` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Fix the renta registry data or engine per the diagnosis with AEAT/BOE grounding and rerun the registry suite sequentially

## Scope

- `registry renta surfaces`

## Description

- Re-ran the registry suite sequentially at HEAD before editing; 56 failures
  reproduced (55 real plus the loader-cache cross-session infra test).
- Root cause of the dominant cluster: the M100 2025 estimacion-directa
  rendimiento formula (casilla 0224) gates on the binding
  `renta-2025-profile-has-economic-activity`, which the production profile
  resolver `_resolve_one` always supplies (1/0 from
  `taxpayer_type.irpf_income_categories`). The peer renta campaign added the
  gate and updated the shared scenario support module but left ~11 individual
  2025 test helpers under-supplying it; supplied the production-guaranteed
  input in every helper (expectations unchanged).
- Fixed the corpus-path resolution production bug: `_resolve_corpus_path`
  and `_source_evidence_roots` still probed the retired `src/aeat/_data`
  fallback after the package-root rename, so every non-companion text source
  reported "missing corpus file". Retargeted both to `src/cadrumo/_data`.
  These five findings were NOT stale-cache artefacts (the S01 diagnosis's
  cache theory did not hold once re-verified at HEAD); they were real content
  defects requiring code/data edits.
- Grounded the anexo-c base-liquidable-general-negativa expectation on
  Ley 35/2006 art. 50.3 (the 4-year carry-forward of a negative base
  liquidable general), matching the registry's authored comment and BOE; the
  test still expected art. 48 (within-year integracion, a distinct mechanism).
- Synced the M210 2025 completeness manifest with the art-13.1 closure ref
  (the base TRLIRNR income-scope paragraph the casilla and binding cite).
- Removed the retired `ley-37-1992.json` normative summary straggler (the
  authoritative consolidated HTML corpus is retained).
- Resolved the chain-cohesion vs value-consumption tension: the M131
  rendimiento-neto-modulos fold is value-consumed by M100 income so it must
  keep `direct_calculation`; refined the chain-cohesion gate to require at
  least one contract-shaped role per canonical chain rather than every
  relation (superseding an interim factual_evidence reclassification).
- Enrolled `LEDGER_IRNR_INCOME_AGGREGATION` in the selector-shape coverage
  gate (fully-registered typed source the M210 IRNR feature landed).
- Re-ran the full registry suite sequentially: green except the P05-owned
  loader-cache cross-session infra test (passes isolated; fails only under
  full-suite ordering).

## Outcome

Registry renta cluster GREEN sequentially (2971 passed, 7 deselected). The one
residual `-n 0` full-suite failure,
`test_loader_cache_isolation::test_bundled_root_disk_cache_survives_across_separate_real_pytest_sessions`,
is a pre-existing test-ordering pollution issue (passes in isolation, was red
before any edit this campaign) and is explicitly P05.S10's scope, not the renta
cluster. Commits: `52352c8d61` (profile-binding test fixtures), `de1dfced37`
(corpus-path src/cadrumo), `38f5c2e3a3` (anexo-c art-50.3), `0bfed537f9` (M210
art-13.1 manifest), `b791f52011` (retired ley-37-1992.json removal),
`f946280690` (M131 direct_calculation + chain-cohesion invariant), `5c60977022`
(selector-shape IRNR enrollment).

## Notes

- Engine-vs-expectation classification: the dominant cluster was a
  test-fixture under-supply (production always supplies the binding), NOT an
  expectation-number edit; the anexo-c and chain-cohesion fixes corrected stale
  test EXPECTATIONS against BOE/registry authority; the corpus-path, M210
  manifest, ley-37-1992, and M131 items were registry/production data fixes.
- The S01 diagnosis attributed five of these to stale cross-session cache; on
  re-verification at HEAD they were real content defects. Re-running before
  trusting the prior conclusion (per the swarm re-read-HEAD rule) surfaced this.
- No destructive git; every commit used an explicit pathspec. The application
  cascade (S03) is handled separately.
