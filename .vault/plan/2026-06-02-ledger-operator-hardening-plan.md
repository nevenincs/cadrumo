---
tags:
  - '#plan'
  - '#ledger-operator-hardening'
date: '2026-06-02'
tier: L3
related:
  - '[[2026-06-02-ledger-operator-hardening-adr]]'
  - '[[2026-05-08-ledger-renta-pipeline-adr]]'
  - '[[2026-05-14-ledger-transaction-lifecycle-adr]]'
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

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #plan) and one feature tag.
     Replace ledger-operator-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.
     tier is mandatory for new plans. Allowed: L1, L2, L3, L4.
     L1 = Steps only. L2 = Phases above Steps. L3 = Waves above
     Phases above Steps. L4 = Epic above Waves above Phases above
     Steps; PM association required. Pre-existing plans without this
     field default to L2.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar]]'. The related field
     carries the AUTHORISING documents (ADR, research, reference, prior
     plan) for every Step in this plan; Steps inherit this chain;
     per-row reference footers do not exist.

     DO NOT add frontmatter fields
     outside the frontmatter. -->


<!-- HIERARCHY AND TIERS:
     Epic > Wave > Phase > Step. Step is the canonical leaf-row
     noun. Execution-log artifact: <Step Record>.
     Tier is declared in frontmatter as tier: L1/L2/L3/L4
     (mandatory for new plans; pre-existing plans without the
     field default to L2 and the writer adds the field on first
     edit). The tier selects containers:
       L1 = Steps only.
       L2 = Phases above Steps.
       L3 = Waves above Phases above Steps.
       L4 = Epic above Waves above Phases above Steps; MUST declare
            a project-management association in the Epic intent
            block prose.
     Selection is by complexity criteria, not container counting.
     Writer never invents containers to qualify a tier. -->

<!-- IDENTIFIERS AND ROW CONTRACT:
     S##, P##, W## are flat, per-document, append-only, immutable.
     Promotion adds containers without renumbering. Gaps are not
     reused.
     Display paths are computed from current grouping:
       Step path:    L1 S##   L2 P##.S##   L3/L4 W##.P##.S##
       Phase heading:        L2 P##       L3/L4 W##.P##
       Wave heading:                      L3/L4 W##
     Row format:
       - [ ] `<display-path>` - imperative-verb action; `path/to/file`.
     Two-state checkboxes only ([ ] open, [x] closed). No per-row
     reference footers; wiki-links and markdown links are forbidden
     in plan body. Authorising documents go in the plan's `related:`
     frontmatter once.
     ASCII spaced hyphens everywhere; em-dash (U+2014) and en-dash
     (U+2013) are forbidden. Step rows within a Phase are
     contiguous. -->

<!-- NO COMPRESSION:
     N self-similar actions = N rows. Never collapse into "for each
     X, do Y" / "across all callers, do Z" / "in every module,
     replace W". The rule applies at every tier including L1. -->

<!-- VAULTSPEC-CORE VAULT PLAN CLI:
     The `vaultspec-core vault plan` CLI is the canonical surface for
     structural manipulation of this plan document. Writers and
     executors MUST use `vaultspec-core vault plan step add/insert/move/
     remove/check/uncheck/toggle/edit`,
     `vaultspec-core vault plan phase add/move/remove/edit`,
     `vaultspec-core vault plan wave add/move/remove/edit`,
     `vaultspec-core vault plan epic intent`, and
     `vaultspec-core vault plan tier promote/demote` for every
     identifier-affecting change rather than hand-editing the row
     grammar. Hand edits are tolerated by the parser but flagged by
     `vaultspec-core vault plan check`; canonical-identifier preservation is
     guaranteed only when the CLI performs the mutation. See the
     CLI ADR (2026-05-06-plan-hardening-adr) for the full
     subcommand surface. -->

# `ledger-operator-hardening` `ledger operator-testimonial corpus and persona-driven hardening` plan

## Wave `W01` - Corpus foundation

Hand-author the calculation-grounded raw corpus and the oracle, and lock them with a fidelity test.

<!-- One-line headline summary plan. -->

### Phase `W01.P01` - Raw corpus authoring

Four raw bank exports, 500+ rows, 2025 H1 to 2026 H1, full taxonomy coverage.

- [x] `W01.P01.S01` - Author BBVA business EUR raw CSV (181 rows); `src/aeat/tests/fixtures/financial/ledger-corpus/bbva-business-eur.csv`.
- [x] `W01.P01.S02` - Author CaixaBank personal EUR raw CSV (149 rows); `src/aeat/tests/fixtures/financial/ledger-corpus/caixabank-personal.csv`.
- [x] `W01.P01.S03` - Author Revolut multi-currency raw CSV (GBP/USD/EUR); `src/aeat/tests/fixtures/financial/ledger-corpus/revolut-multi.csv`.
- [x] `W01.P01.S04` - Author N26 savings EUR raw CSV (79 rows); `src/aeat/tests/fixtures/financial/ledger-corpus/n26-savings.csv`.
- [x] `W01.P01.S05` - Top corpus past 500 rows and verify all 16 IvaCategory + 43 SpendingCategory covered; `src/aeat/tests/fixtures/financial/ledger-corpus/`.

### Phase `W01.P02` - Ground-truth manifest oracle

Per-transaction oracle keyed by natural key plus per-modelo aggregate base sums.

- [x] `W01.P02.S06` - Author per-transaction oracle for all four accounts; `src/aeat/tests/fixtures/financial/ledger-corpus/ground-truth.manifest.json`.
- [x] `W01.P02.S07` - Author per-modelo aggregate base sums (303/130/100/390) per period; `src/aeat/tests/fixtures/financial/ledger-corpus/ground-truth.manifest.json`.
- [ ] `W01.P02.S08` - Author derived classify --from-csv oracle inputs; `src/aeat/tests/fixtures/financial/ledger-corpus/classify/`.

### Phase `W01.P03` - Corpus-fidelity test

Import, classify, aggregate, assert projections and base sums equal the oracle.

- [x] `W01.P03.S09` - Wire CurrencyNormalizationService with ECB rates for corpus foreign-currency dates; `src/aeat/tests/test_ledger_corpus_fidelity.py`.
- [x] `W01.P03.S10` - Corpus-fidelity test: per-row projections and aggregate base sums equal the oracle; `src/aeat/tests/test_ledger_corpus_fidelity.py`.

## Wave `W02` - Operator-journey CI suites

Encode the ledger CLI workflows as durable pytest journeys verifying against the oracle.

### Phase `W02.P04` - Import and multicurrency journeys

Provider import, dedup, dry-run, ECB normalization journeys.

- [x] `W02.P04.S11` - Import journey: four providers, dedup, likely-duplicate, dry-run; `src/aeat/entrypoints/cli/test_ledger_journeys.py`.
- [x] `W02.P04.S12` - Multicurrency normalization journey (GBP/USD to EUR via ECB); `src/aeat/entrypoints/cli/test_ledger_journeys.py`.

### Phase `W02.P05` - Classify, allocate, ratios journeys

Single and bulk classification, proportionality, per-category ratio overrides.

- [x] `W02.P05.S13` - Single classify journey (iva_category, EU member state, MIXED business_pct); `src/aeat/entrypoints/cli/test_ledger_journeys.py`.
- [x] `W02.P05.S14` - Bulk classify --from-csv journey resolving ids at runtime; `src/aeat/entrypoints/cli/test_ledger_journeys.py`.
- [x] `W02.P05.S15` - Allocate plus ratios set/unset/validate/eligible journey; `src/aeat/entrypoints/cli/test_ledger_journeys.py`.

### Phase `W02.P06` - Filter, search, review, batch-edit journeys

Operating-scale filtering, search, and iterative batch amendment.

- [x] `W02.P06.S16` - Filter/review typed-spec journey at operating scale; `src/aeat/entrypoints/cli/test_ledger_journeys.py`.
- [x] `W02.P06.S17` - Search journey across description/counterparty/category; `src/aeat/entrypoints/cli/test_ledger_journeys.py`.
- [x] `W02.P06.S18` - Batch-edit journey: iterative refinement over hundreds of rows; `src/aeat/entrypoints/cli/test_ledger_journeys.py`.

### Phase `W02.P07` - Lifecycle journeys

Split, merge, archive, stash, remove, history, track.

- [x] `W02.P07.S19` - Split parent into children and re-merge journey; `src/aeat/entrypoints/cli/test_ledger_journeys.py`.
- [x] `W02.P07.S20` - Archive/stash/remove plus history/track lineage journey; `src/aeat/entrypoints/cli/test_ledger_journeys.py`.

### Phase `W02.P08` - Export fidelity and verify journeys

CSV/JSON/XLSX roundtrip, preflight, status, verify gate vs oracle.

- [x] `W02.P08.S21` - Export CSV/JSON/XLSX roundtrip fidelity journey; `src/aeat/entrypoints/cli/test_ledger_journeys.py`.
- [x] `W02.P08.S22` - Preflight/status/verify gate journey verified against oracle; `src/aeat/entrypoints/cli/test_ledger_journeys.py`.

## Wave `W03` - Persona testimonials and hardening

Drive the live CLI via agent personas, persist testimonials, and absorb findings as hardening Steps.

### Phase `W03.P09` - Persona testimonials

Agent personas drive the live CLI end-to-end and persist vault testimonials.

- [ ] `W03.P09.S23` - Persona: freelance autonoma quarterly-close testimonial; `.vault/audit/`.
- [ ] `W03.P09.S24` - Persona: asesor fiscal multi-client review testimonial; `.vault/audit/`.
- [ ] `W03.P09.S25` - Persona: multi-currency consultant testimonial; `.vault/audit/`.
- [ ] `W03.P09.S26` - Persona: year-end M100 reviewer testimonial; `.vault/audit/`.

### Phase `W03.P10` - Honesty review and finding absorption

Fresh-context honesty review; turn findings into hardening Steps with gates.

- [x] `W03.P10.S27` - Fresh-context honesty review of campaign close; `.vault/audit/`.
- [x] `W03.P10.S28` - Absorb testimonial findings as hardening Steps with verification gates; `.vault/plan/2026-06-02-ledger-operator-hardening-plan.md`.
- [ ] `W03.P10.S31` - Harden bulk classify --from-csv to load-once/save-once (O(n) re-encryption: 270 rows = 404s); `perf gate 270 rows under 30s; `src/aeat/application/ledger/_actions.py`.
- [ ] `W03.P10.S32` - Add an XLSX/Google-Sheets export path for the Drive goal (export surface is csv/jsonl only, no xlsx verb); `src/aeat/adapters/outbound/google/`.
- [ ] `W03.P10.S33` - Provide a transfer-reclassification helper/journey (import never emits INTERNAL_TRANSFER; `transfers land OUTGOING/INCOMING NOT_YET_PROCESSED); `src/aeat/entrypoints/cli/_ledger.py`.

## Wave `W04` - Deferred live Google export

Parked until explicit operator go-ahead: live Drive/Gmail export and manual review.

### Phase `W04.P11` - Live Drive and Gmail export

Deferred: live Drive upload, manual review, Gmail/Drive document links.

- [ ] `W04.P11.S29` - Live Drive export plus manual review (deferred, on go-ahead); `src/aeat/adapters/outbound/google/`.
- [ ] `W04.P11.S30` - Gmail/Drive document-link workflow (deferred, on go-ahead); `src/aeat/adapters/outbound/google/`.

## Wave `W05` - LLM classification testing

Drive the LLM auto-classifier over the corpus and score predictions against the ground-truth oracle.

### Phase `W05.P12` - LLM classification accuracy

Score LLM predictions against the oracle and capture edge-case behaviour.

- [ ] `W05.P12.S34` - Classify corpus descriptions via the LLM classifier and score predictions against the ground-truth oracle (accuracy per category); `src/aeat/tests/test_ledger_corpus_llm_classification.py`.
- [ ] `W05.P12.S35` - Record classified_by=llm:<model> and confidence; `flag low-confidence rows for manual review; `src/aeat/tests/test_ledger_corpus_llm_classification.py`.
- [ ] `W05.P12.S36` - Capture LLM behaviour on edge cases (recargo anomaly, transfers, foreign reverse-charge, regimen simplificado); `src/aeat/tests/test_ledger_corpus_llm_classification.py`.
- [ ] `W05.P12.S37` - Gate: per-IvaCategory/SpendingCategory LLM misclassification rate tracked against a threshold; `src/aeat/tests/test_ledger_corpus_llm_classification.py`.

## Wave `W06` - Tax-fact manipulations: split, IVA/IRPF base-rate, proportionality

Exercise per-row tax-fact edits and assert the modelo projections recompute correctly.

### Phase `W06.P13` - Tax-fact manipulations

Per-row split / rate / proportionality / irpf edits with modelo recompute assertions.

- [ ] `W06.P13.S38` - Split a mixed invoice into business and personal children with per-child base/IVA split; `src/aeat/entrypoints/cli/test_ledger_corpus_journeys.py`.
- [ ] `W06.P13.S39` - Re-derive base/IVA from gross at 21/10/4 and assert M303 soportado/repercutido recompute; `src/aeat/tests/test_ledger_corpus_fidelity.py`.
- [ ] `W06.P13.S40` - Change business_pct and per-category usage ratio and assert deducible-base proportionality propagates; `src/aeat/tests/test_ledger_corpus_fidelity.py`.
- [ ] `W06.P13.S41` - Reassign irpf_category (trabajo<->actividad) and assert M130/M100 routing changes; `src/aeat/tests/test_ledger_corpus_fidelity.py`.

## Wave `W07` - Import and export

Multi-format provider import parity, cross-format dedup, and export roundtrip fidelity.

### Phase `W07.P14` - Multi-format import/export fidelity

Provider parity, cross-format dedup, export roundtrip.

- [ ] `W07.P14.S42` - Import OFX/XLSX/PDF provider formats and assert parity with CSV import; `src/aeat/entrypoints/cli/test_ledger_corpus_journeys.py`.
- [ ] `W07.P14.S43` - Cross-format re-import dedups by import_fingerprint (likely-duplicate warning); `src/aeat/entrypoints/cli/test_ledger_corpus_journeys.py`.
- [ ] `W07.P14.S44` - Export csv/jsonl and assert roundtrip fidelity back through import; `src/aeat/entrypoints/cli/test_ledger_corpus_journeys.py`.

## Wave `W08` - Transaction modification lifecycle

Edit, reclassify, re-allocate, and lifecycle transitions with lineage and finalized-modelo guards.

### Phase `W08.P15` - Transaction modification lifecycle

Edit/reclassify/re-allocate with lineage and finalized-modelo guard.

- [ ] `W08.P15.S45` - Update editable facts (date/amount/counterparty/description) and assert edit_lineage chain; `src/aeat/entrypoints/cli/test_ledger_corpus_journeys.py`.
- [ ] `W08.P15.S46` - Reclassify and re-allocate after review and assert classification_history retained; `src/aeat/entrypoints/cli/test_ledger_corpus_journeys.py`.
- [ ] `W08.P15.S47` - Modification refused when the row feeds a finalized modelo (blocking-reference guard); `src/aeat/entrypoints/cli/test_ledger_corpus_journeys.py`.

## Wave `W09` - Calculation-engine recalculation on post-publish ledger change

When a contributing ledger row changes after a modelo is drafted/published, dependents go stale and recompute; finalized modelos block destructive source edits.

### Phase `W09.P16` - Ledger-change recalculation propagation

Post-publish ledger edits go stale and recompute; finalized modelos block source edits.

- [ ] `W09.P16.S48` - Draft a modelo revision from the ledger, then modify a contributing ledger row; `src/aeat/tests/test_ledger_modelo_staleness.py`.
- [ ] `W09.P16.S49` - Assert dependents are stamped stale and recalculation is triggered (no silent stale revision); `src/aeat/tests/test_ledger_modelo_staleness.py`.
- [ ] `W09.P16.S50` - Assert a finalized/published modelo blocks destructive ledger edits to its source rows; `src/aeat/tests/test_ledger_modelo_staleness.py`.

## Wave `W10` - Ledger-snapshot-backed modelo filing (ADR-driven, every modelo)

Back every verified/filed modelo revision with an immutable content-addressed ledger snapshot; detect drift; uniform across all modelos.

### Phase `W10.P17` - Snapshot model and capture

Typed LedgerFilingSnapshot record, deterministic fingerprint, optional revision field.

- [x] `W10.P17.S51` - Define LedgerFilingSnapshot record (per-contributor row fingerprints + aggregate snapshot fingerprint + captured_at) and a pure compute helper; `src/aeat/domain/modelos/_ledger_filing_snapshot.py`.
- [x] `W10.P17.S52` - Add optional ledger_filing_snapshot field to CalculationRevision (default None, legacy-safe, excluded from the revision-id hash); `src/aeat/domain/modelos/_calculation_revision.py`.
- [x] `W10.P17.S53` - Strict roundtrip + fingerprint-determinism + anti-tautology tests for the snapshot record; `src/aeat/domain/modelos/test_ledger_filing_snapshot.py`.

### Phase `W10.P18` - Staleness evaluation and events

Pure drift evaluator + stale event + work-unit marker.

- [x] `W10.P18.S54` - Implement evaluate_ledger_filing_staleness classifying each contributor unchanged/changed/removed against the live catalogue; `src/aeat/domain/modelos/_ledger_filing_snapshot.py`.
- [ ] `W10.P18.S55` - Add BucketEventType.MODELO_LEDGER_DEPENDENT_STAMPED_STALE and a work-unit stale marker mirroring the censo pattern; `src/aeat/domain/buckets/_event.py`.
- [x] `W10.P18.S56` - Tests: mutate a contributing row -> stale detected; `empty-set (non-ledger) snapshot trivially stable; `src/aeat/domain/modelos/test_ledger_filing_snapshot.py`.

### Phase `W10.P19` - Verify/file wiring and uniform modelo coverage

Capture at verify/file, surface drift, prove every-modelo uniformity.

- [x] `W10.P19.S57` - Capture the snapshot at VERIFICADO_COMPLETO and re-affirm at PRESENTADO in the calculate/verify/file flow; `src/aeat/application/modelos/`.
- [ ] `W10.P19.S58` - Surface staleness in ledger/modelo status, verify, and check outputs; `src/aeat/entrypoints/cli/`.
- [ ] `W10.P19.S59` - Every-modelo coverage test: ledger-fed (303/130/100) and a non-ledger modelo each carry a uniform snapshot; `filed snapshot is immutable; `src/aeat/application/modelos/test_modelo_filing_snapshot_coverage.py`.

## Description

<!-- Briefly describe the proposed work. Reference `{adr}`s,
`{research}`, `{reference}`. Supporting documentation must be read prior to
writing the plan document. -->

## Steps

<!-- The plan's tier (declared in frontmatter as `tier: L1`, `L2`, `L3`, or
`L4`) determines the structure under this section:

- `L1`: a flat list of Step rows (no Phase, Wave, or Epic).
- `L2`: one or more `### Phase` blocks each containing Step rows.
- `L3`: one or more `## Wave` blocks each containing Phase blocks.
- `L4`: a `## Epic intent` block, followed by Wave blocks. -->

<!-- Replace this scaffold with the tier-appropriate structure for your plan.
Format examples for each block type are embedded below as commented
templates. -->

<!-- IMPORTANT: This document must be updated between execution runs to
     track progress. -->

<!-- PHASE BLOCK FORMAT (L2, L3, L4):
     ### Phase `P02` - rewrite the writer-agent contract

     One sentence stating what this Phase delivers.

     - [ ] `P02.S01` - imperative-verb action; `path/to/file`.
     - [ ] `P02.S02` - imperative-verb action; `path/to/file`.

     At L3/L4 the Phase heading uses the ancestor-aware path
     (### Phase `W01.P02` - ...). The intent sentence is mandatory. -->

<!-- WAVE BLOCK FORMAT (L3, L4):
     ## Wave `W01` - language-only convention rollout

     One paragraph stating what this Wave delivers, which downstream
     Wave depends on it, and which authorising documents back it.

     ### Phase `W01.P01` - ...
     ### Phase `W01.P02` - ...

     The Wave intent paragraph is mandatory. -->

<!-- EPIC INTENT BLOCK FORMAT (L4 only):
     ## Epic intent

     One paragraph stating the strategic goal, the external project-
     management association (milestone name, project board identifier,
     roadmap entry), the timeline horizon, and the teams or agents
     involved.

     ## Wave `W01` - ...
     ## Wave `W02` - ...

     The ## Epic intent block is mandatory at L4 and absent at L1, L2,
     L3. The plan title (the level-one # heading at the top of the
     document) is the Epic title; no separate Epic heading is emitted. -->

## Parallelization

<!-- State which Steps, Phases, or Waves can be executed in parallel and
which carry hard ordering. At `L1` and `L2`, parallelism is decided
per-Step or per-Phase. At `L3` and `L4`, Waves are sequenced by
default (one Wave must land before the next can begin); Phases
within a single Wave may be parallelised when they share no hard
interdependency. -->

## Verification

<!-- State the mission success criteria for this plan. Each criterion
should be a verifiable check (test passes, surface conforms,
reviewer signs off) rather than a free-form assertion.

The plan is complete when every Step in every Wave is closed
(`- [x]`). At `L4`, the Epic-completion check additionally requires
the declared project-management association to report the Epic
complete.

For tier-specific verification cadence, see the convention ADR
authorising this plan via the `related:` frontmatter. -->
