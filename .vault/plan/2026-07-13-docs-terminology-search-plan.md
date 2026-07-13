---
tags:
  - '#plan'
  - '#docs-terminology-search'
date: '2026-07-13'
modified: '2026-07-13'
tier: L3
related:
  - '[[2026-07-13-docs-terminology-search-adr]]'
  - '[[2026-06-10-docs-terminology-search-research]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `docs-terminology-search` plan

## Wave `W01` - Measure

Ground every later decision in committed measurements: corpus coverage of the shipped relevance mapping, the held-out miss-rate baseline, and the synonym ratification queue state.

### Phase `W01.P01` - Coverage, miss-rate, and queue reports

Read-only measurement runs against the resident RAG service producing committed reports.

- [x] `W01.P01.S01` - Generate the coverage report: derive the candidate query surface from calc-grade casilla labels/sections and legal-catalogue provision vocabulary, list every derivable target with no inbound relevance entry, and commit the report; `dev/docs/terminology/, .vault/audit/`.
- [x] `W01.P01.S02` - Run the held-out golden queries through the shipped relevance mapping with the miss-rate machinery and commit the baseline miss-rate report; `dev/docs/terminology/_miss_rate.py, .vault/audit/`.
- [x] `W01.P01.S03` - Inventory the synonym candidate queue (mined, unratified) and commit the inventory with a ratify-or-clear disposition per candidate; `dev/docs/terminology/_synonym_mining.py, .vault/audit/`.

## Wave `W02` - Hook wiring

Wire the repo extractors into the shipped upstream vaultspec-rag preprocess seam, prove per-kind parity against the committed sidecars, then cut over atomically and retire the sidecar tree.

### Phase `W02.P02` - Adapter, rules, parity, cutover

Build the upstream-schema adapter and rule file, gate config validity, prove parity per source kind, then one atomic cutover commit.

- [x] `W02.P02.S04` - Implement the upstream-schema adapter: serialize the repo PreprocessOutput to the upstream PreprocOutput JSON contract behind a python -m entry point, with unit tests against the pinned schema major; `dev/docs/preprocess/`.
- [x] `W02.P02.S05` - Author the preprocess rule file for the four corpus source kinds and add the strict preprocess-check repo gate test; `.vaultragpreprocess.toml, dev/docs/preprocess/tests/`.
- [x] `W02.P02.S06` - Prove per-kind parity: preprocess run-one output text equals the committed sidecar text for a representative source of each kind, asserted by a committed test; `dev/docs/preprocess/tests/`.
- [x] `W02.P02.S07` - Re-scoped cutover (ADR Update 1): exclude the extracted sidecars from the dev index via .vaultragignore, retarget the terminology resolver path rules to source-file paths, correct the stale preprocess docstring to describe the sidecars' product-payload role, keep the hook-vs-sidecar parity gate as a permanent lock, and prove an equal-or-superset sweep target set - one explicit-path commit; `the sidecar tree stays (it is the wheel's corpus payload and the shipped search's index source); `.vaultragignore, dev/docs/terminology/_resolution.py, dev/docs/preprocess/__init__.py, dev/docs/preprocess/tests/test_hook.py`.

## Wave `W03` - Widen

Extend the sweep query vocabulary from the coverage report over the bundled legal corpus and casilla registry, re-run the sweep, and land the widened relevance mapping as a reviewed diff.

### Phase `W03.P03` - Vocabulary widening and sweep re-run

Author the widened query vocabulary from the coverage report, reindex, sweep, wrangle, and land the reviewed mapping diff.

- [x] `W03.P03.S08` - Author the widened query vocabulary from the coverage report through the Handbook enrolment surfaces, keeping the synonym ratification ratchet; `src/cadrumo/_data/terminology/`.
- [x] `W03.P03.S09` - Run incremental reindex then the widened sweep through the resident service, wrangle through the typed resolution, and land the widened relevance mapping as a reviewed committed diff; `src/cadrumo/_data/terminology/relevance/relevance.json`.

## Wave `W04` - Rung-2 gate

Take the deferred rung-2 decision on the post-widening miss-rate number per ADR D3 and commit the measurement either way.

### Phase `W04.P04` - Gate decision

Re-measure the held-out miss-rate post-widening and apply the ADR D3 numeric gate.

- [x] `W04.P04.S10` - Re-run the held-out miss-rate over the widened mapping, commit the measurement, and apply the ADR D3 gate: implement rung 2 only above the ten-percent top-five miss line, else record the standing baseline; `dev/docs/terminology/, .vault/audit/`.

## Description

## Steps

## Parallelization

## Verification
