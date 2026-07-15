---
tags:
  - '#plan'
  - '#docs-lifecycle-tutorials'
date: '2026-07-13'
modified: '2026-07-15'
tier: L2
related:
  - '[[2026-07-13-docs-lifecycle-tutorials-adr]]'
  - '[[2026-07-13-docs-lifecycle-tutorials-research]]'
---

# `docs-lifecycle-tutorials` plan

### Phase `P01` - Condense and merge the existing how-to surface

Execute the ratified disposition table's merges, retirement, and extraction landings so every receiving page tightens rather than grows

- [x] `P01.S01` - Merge filing-periods.md into filing-calendar.md as a period-tokens-and-dates subsection; `sweep inbound links; delete the merged page; `docs/how-to/filing-calendar.md docs/how-to/filing-periods.md`.
- [x] `P01.S02` - Merge review-queue.md into classify-transactions.md as a what-still-needs-a-decision subsection; `sweep inbound links; delete the merged page; `docs/how-to/classify-transactions.md docs/how-to/review-queue.md`.
- [x] `P01.S03` - Merge classify-with-llm.md, classify-with-llm-evidence.md, and setup-llm-classification.md into one consolidated LLM-assisted-classification page; `sweep inbound links; delete the merged pages; `docs/how-to/classify-with-llm.md docs/how-to/classify-with-llm-evidence.md docs/how-to/setup-llm-classification.md`.
- [x] `P01.S04` - Merge justificante-receipts.md into reconcile.md as a leading pull-and-store-the-justificante section; `sweep inbound links; delete the merged page; `docs/how-to/reconcile.md docs/how-to/justificante-receipts.md`.
- [x] `P01.S05` - Retire read-live-aeat-data.md, redistributing its live-pull content to check-aeat-notifications.md, censo-update.md, and reconcile.md; `sweep inbound links; `docs/how-to/read-live-aeat-data.md docs/how-to/check-aeat-notifications.md docs/how-to/censo-update.md docs/how-to/reconcile.md`.
- [x] `P01.S06` - Land the extracted explanation-page signals tightened on their receiving pages (verify-state taxonomy, revision immutability, xlsx-vs-Sheets, fingerprint purpose, reconcile scope, mixed-cost splitting, import readiness); `docs/how-to/verification-reports.md docs/how-to/filing-spine.md docs/how-to/review-with-google-sheets.md docs/how-to/file-at-aeat.md docs/how-to/reconcile.md docs/how-to/classify-transactions.md docs/how-to/import-bank-statements.md`.
- [x] `P01.S07` - Trim the five explanation pages to tightened conceptual cores now that their actionable signal has confirmed homes; `add the this-page-covers opening paragraph to every touched page; `docs/explanation`.

### Phase `P02` - Author the Tier-1 modelo pages

Fill the operator-named per-modelo gaps (130, 100, 349) on the modelo-303 template with live-verified commands

- [x] `P02.S08` - Author docs/how-to/modelo-130.md on the modelo-303 template with live-verified commands and the this-page-covers opening; `docs/how-to/modelo-130.md`.
- [x] `P02.S09` - Author docs/how-to/modelo-100.md as a condensed how-to cross-linking the Renta deep-dive for mechanism, with live-verified commands including the annual period token; `docs/how-to/modelo-100.md`.
- [x] `P02.S10` - Author docs/how-to/modelo-349.md covering the intra-community recapitulative flow with live-verified commands; `docs/how-to/modelo-349.md`.

### Phase `P03` - Author the Renta deep-dive document

Author the one sanctioned deep-mechanism explanation page covering the Renta filing and its bindings

- [x] `P03.S11` - Author explanation/renta-and-bindings.md: the labelled deep-dive on how the Renta filing builds from the ledger, the Modelo 130 fold-in, profile facts, registry bindings, cross-period carry, and visible-gaps-not-guessed-zeros; `ground every command against the live bindings/dependencies/observations surface; `docs/explanation/renta-and-bindings.md`.

### Phase `P04` - Author the two lifecycle tutorials

Author the IRPF-year and IVA-year on-rails tutorials over one shared persona and continuous ledger dataset

- [x] `P04.S12` - Author tutorials/irpf-lifecycle.md: setup, four quarterly Modelo 130 stages with cumulative carry, annual Modelo 100 close via cross-period fold-in, file and reconcile; `absorb the existing tutorials/index.md walkthrough as the first-quarter stage; `docs/tutorials/irpf-lifecycle.md docs/tutorials/index.md`.
- [x] `P04.S13` - Author tutorials/iva-lifecycle.md: setup with optional prorrata, quarterly Modelo 303 stages with IVA-wallet seed and credit carry, optional Modelo 349 branch, annual Modelo 390 reconciliation, file and reconcile; `same persona and continuous dataset as the IRPF tutorial; `docs/tutorials/iva-lifecycle.md`.
- [x] `P04.S14` - Convert tutorials/index.md into a short index introducing the two lifecycle tutorials and the shared persona; `docs/tutorials/index.md`.

### Phase `P05` - Restructure indexes, run gates, close with honesty review

Regroup the how-to index and landing grid on the filing-year axes, pass the conformance and Sphinx gates, and run the mandated campaign-close honesty review

- [x] `P05.S15` - Regroup docs/how-to/index.md and the landing-page route grid on the filing-year axes (entry points, profile, calendar, ledger, filings, residuals) per the ratified disposition table; `docs/how-to/index.md docs/index.md`.
- [x] `P05.S16` - Run the documented-command conformance gate and the Sphinx nitpicky build gate; `fix every failure the campaign's edits caused; `docs src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py dev/docs/tests/test_docs_build.py`.
- [x] `P05.S17` - Run the mandated fresh-context campaign-close honesty review; `persist it as a vault audit and open follow-up steps for every surfaced item; `.vault/audit`.
- [x] `P05.S18` - Retire the three stray project-management files from the docs root (ADRS.md, USERDOCS-KICKOFF-BRIEF.md, HARNESS-USERDOCS-KICKOFF-BRIEF.md) per docs-architecture ADR clause 3a; `docs/ADRS.md docs/USERDOCS-KICKOFF-BRIEF.md docs/HARNESS-USERDOCS-KICKOFF-BRIEF.md`.
- [x] `P05.S19` - Replay both lifecycle tutorials end-to-end against a sandbox profile and reconcile the narrated figures with real command output; `docs/tutorials/irpf-lifecycle.md docs/tutorials/iva-lifecycle.md`.

## Description

Execute the accepted docs-lifecycle-tutorials ADR: restructure the user
documentation around the taxpayer's filing year. Phase P01 performs the
condense pass from the research's ratified disposition table (7 page merges,
one retirement, the explanation-signal extraction landings, and the
explanation-page trims). Phases P02 to P04 author the targeted new material:
the three Tier-1 modelo how-to pages (130, 100, 349), the sanctioned Renta
deep-dive explanation document, and the two lifecycle tutorials (IRPF year,
IVA year) over one shared persona and continuous ledger dataset. Phase P05
regroups the indexes on the filing-year axes, passes the conformance and
Sphinx gates, and closes with the mandated honesty review. Standing
conventions binding every step: condense, never bloat; every touched page
opens with a one-paragraph "This page covers the ..." summary; every cited
CLI verb is verified against the live surface at authoring time; user-facing
language stays simple, singular, imperative, taxpayer-general. Documentation
prose is authored by the coordinating session itself; subagents contribute
research, grounding verification, and read-only review only.

## Steps

## Parallelization

P01 steps S01 to S05 (the merges and the retirement) are independent of one
another; S06 depends on nothing but must land before S07 (the explanation
trims require the extracted signal to have confirmed homes). P02 and P03 may
run in parallel after P01, but P02.S09 (modelo-100.md) cross-links the Renta
document and should land after or alongside P03.S11. P04 depends on P02 and
P03 (the tutorials link to the modelo pages and the Renta document);
P04.S14 depends on P04.S12 and P04.S13. P05 is strictly last and its steps
run in order. Because a single session authors all prose, phases execute
sequentially in practice; the parallelism above marks safe commit
interleavings, not concurrent authorship.

## Verification

- The documented-command conformance gate passes:
  `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py -m integration`.
- The Sphinx nitpicky build gate passes:
  `uv run --no-sync pytest dev/docs/tests/test_docs_build.py`.
- No merged or retired page remains referenced by any surviving page (link
  sweep verified by the Sphinx gate plus a grep for the retired filenames).
- Every touched user-facing page opens with a "This page covers the ..."
  paragraph (grep-verified across docs/how-to, docs/tutorials,
  docs/explanation).
- The two lifecycle tutorials demonstrate cumulative carry, cross-period
  fold-in, IVA-wallet seed and credit carry with live-verified commands.
- The campaign-close honesty review audit exists in .vault/audit and every
  surfaced item is either closed with verification or tracked as a follow-up
  step; the plan is structurally complete only after that gate.
- Every closed step has a matching exec record before it is checked.
