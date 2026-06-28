---
tags:
  - '#plan'
  - '#ledger-operator-hardening'
date: '2026-06-02'
modified: '2026-06-02'
tier: L3
related:
  - '[[2026-06-02-ledger-operator-hardening-adr]]'
  - '[[2026-05-08-ledger-renta-pipeline-adr]]'
  - '[[2026-05-14-ledger-transaction-lifecycle-adr]]'
  - '[[2026-06-04-ledger-operator-hardening-research]]'
---


<!-- RETIRED: W04, P11, P27, S29, S30, S90, S91, S92 -->







# `ledger-operator-hardening` `ledger operator-testimonial corpus and persona-driven hardening` plan

## Wave `W01` - Corpus foundation

Hand-author the calculation-grounded raw corpus and the oracle, and lock them with a fidelity test.


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
- [x] `W01.P02.S08` - Author derived classify --from-csv oracle inputs; `src/aeat/tests/fixtures/financial/ledger-corpus/classify/`.

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

- [x] `W03.P09.S23` - Persona: freelance autonoma quarterly-close testimonial; `.vault/audit/`.
- [x] `W03.P09.S24` - Persona: asesor fiscal multi-client review testimonial; `.vault/audit/`.
- [x] `W03.P09.S25` - Persona: multi-currency consultant testimonial; `.vault/audit/`.
- [x] `W03.P09.S26` - Persona: year-end M100 reviewer testimonial; `.vault/audit/`.

### Phase `W03.P10` - Honesty review and finding absorption

Fresh-context honesty review; turn findings into hardening Steps with gates.

- [x] `W03.P10.S27` - Fresh-context honesty review of campaign close; `.vault/audit/`.
- [x] `W03.P10.S28` - Absorb testimonial findings as hardening Steps with verification gates; `.vault/plan/2026-06-02-ledger-operator-hardening-plan.md`.
- [x] `W03.P10.S31` - Harden bulk classify --from-csv to load-once/save-once (O(n) re-encryption: 270 rows = 404s); `perf gate 270 rows under 30s; `src/aeat/application/ledger/_actions.py`.
- [x] `W03.P10.S32` - Add an XLSX/Google-Sheets export path for the Drive goal (export surface is csv/jsonl only, no xlsx verb); `src/aeat/adapters/outbound/google/`.
- [x] `W03.P10.S33` - Provide a transfer-reclassification helper/journey (import never emits INTERNAL_TRANSFER; `transfers land OUTGOING/INCOMING NOT_YET_PROCESSED); `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W03.P10.S60` - HIGH: wire CurrencyNormalizationService into the CLI import path so GBP/USD rows convert (value_in_eur/fx_rate) at import instead of silently gating at aggregation; `src/aeat/application/ledger/_actions.py`.
- [x] `W03.P10.S61` - HIGH: project value_in_eur and fx_rate (and rate source) on TransactionPayload so list/review/export surface the EUR-equivalent and FX provenance; `src/aeat/entrypoints/cli/_ledger_payloads.py`.
- [x] `W03.P10.S62` - Add ledger export --period and a period-scoped JSON row list so an operator can hand a gestor just the quarter; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W03.P10.S63` - HIGH: give check/preflight an anomaly channel separate from missing-fact reasons, and a 'non-classification' filtered view, so real anomalies (recargo, gated, foreign) surface without first hand-classifying every row; `src/aeat/application/ledger/_preflight.py`.
- [x] `W03.P10.S64` - Add review --filter classification=business|personal and a readiness dashboard consolidating check + preflight for sign-off; `src/aeat/application/review/_filter.py`.
- [x] `W03.P10.S65` - Add an annual roll-up / M100-readiness surface (full-year ingresos/gastos/net activity totals) and a devengo-vs-caja cross-year reconciliation view; `src/aeat/application/ledger/_preflight.py`.
- [x] `W03.P10.S71` - Project value_in_eur + fx_rate on the export rows (LedgerExportRow) so CSV/JSONL hand-off carries the EUR-equivalent + FX provenance, not only native amounts; `src/aeat/application/ledger/_models.py`.
- [x] `W03.P10.S72` - Support --business-pct in bulk classify --from-csv (extend BulkClassifyRow) so MIXED rows (home-office/vehicle/phone) classify in bulk, not one-at-a-time; `src/aeat/application/ledger/_actions.py`.
- [x] `W03.P10.S73` - Allow importing multiple statement files / a directory in one ledger import invocation (bulk/folder import); `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W03.P10.S74` - Enrich ledger track lineage for imported rows (name the import-batch provenance instead of a bare '-' created bucket event); `src/aeat/entrypoints/cli/_ledger.py`.

## Wave `W05` - LLM classification testing

Drive the LLM auto-classifier over the corpus and score predictions against the ground-truth oracle.

### Phase `W05.P12` - LLM classification accuracy

Score LLM predictions against the oracle and capture edge-case behaviour.

- [x] `W05.P12.S34` - Classify corpus descriptions via the LLM classifier and score predictions against the ground-truth oracle (accuracy per category); `src/aeat/tests/test_ledger_corpus_llm_classification.py`.
- [x] `W05.P12.S35` - Record classified_by=llm:<model> and confidence; `flag low-confidence rows for manual review; `src/aeat/tests/test_ledger_corpus_llm_classification.py`.
- [x] `W05.P12.S36` - Capture LLM behaviour on edge cases (recargo anomaly, transfers, foreign reverse-charge, regimen simplificado); `src/aeat/tests/test_ledger_corpus_llm_classification.py`.
- [x] `W05.P12.S37` - Gate: per-IvaCategory/SpendingCategory LLM misclassification rate tracked against a threshold; `src/aeat/tests/test_ledger_corpus_llm_classification.py`.

## Wave `W06` - Tax-fact manipulations: split, IVA/IRPF base-rate, proportionality

Exercise per-row tax-fact edits and assert the modelo projections recompute correctly.

### Phase `W06.P13` - Tax-fact manipulations

Per-row split / rate / proportionality / irpf edits with modelo recompute assertions.

- [x] `W06.P13.S38` - Split a mixed invoice into business and personal children with per-child base/IVA split; `src/aeat/entrypoints/cli/test_ledger_corpus_journeys.py`.
- [x] `W06.P13.S39` - Re-derive base/IVA from gross at 21/10/4 and assert M303 soportado/repercutido recompute; `src/aeat/tests/test_ledger_corpus_fidelity.py`.
- [x] `W06.P13.S40` - Change business_pct and per-category usage ratio and assert deducible-base proportionality propagates; `src/aeat/tests/test_ledger_corpus_fidelity.py`.
- [x] `W06.P13.S41` - Reassign irpf_category (trabajo<->actividad) and assert M130/M100 routing changes; `src/aeat/tests/test_ledger_corpus_fidelity.py`.

## Wave `W07` - Import and export

Multi-format provider import parity, cross-format dedup, and export roundtrip fidelity.

### Phase `W07.P14` - Multi-format import/export fidelity

Provider parity, cross-format dedup, export roundtrip.

- [x] `W07.P14.S42` - Import OFX/XLSX/PDF provider formats and assert parity with CSV import; `src/aeat/entrypoints/cli/test_ledger_corpus_journeys.py`.
- [x] `W07.P14.S43` - Cross-format re-import dedups by import_fingerprint (likely-duplicate warning); `src/aeat/entrypoints/cli/test_ledger_corpus_journeys.py`.
- [x] `W07.P14.S44` - Export csv/jsonl and assert roundtrip fidelity back through import; `src/aeat/entrypoints/cli/test_ledger_corpus_journeys.py`.

## Wave `W08` - Transaction modification lifecycle

Edit, reclassify, re-allocate, and lifecycle transitions with lineage and finalized-modelo guards.

### Phase `W08.P15` - Transaction modification lifecycle

Edit/reclassify/re-allocate with lineage and finalized-modelo guard.

- [x] `W08.P15.S45` - Update editable facts (date/amount/counterparty/description) and assert edit_lineage chain; `src/aeat/entrypoints/cli/test_ledger_corpus_journeys.py`.
- [x] `W08.P15.S46` - Reclassify and re-allocate after review and assert classification_history retained; `src/aeat/entrypoints/cli/test_ledger_corpus_journeys.py`.
- [x] `W08.P15.S47` - Modification refused when the row feeds a finalized modelo (blocking-reference guard); `src/aeat/entrypoints/cli/test_ledger_corpus_journeys.py`.

## Wave `W09` - Calculation-engine recalculation on post-publish ledger change

When a contributing ledger row changes after a modelo is drafted/published, dependents go stale and recompute; finalized modelos block destructive source edits.

### Phase `W09.P16` - Ledger-change recalculation propagation

Post-publish ledger edits go stale and recompute; finalized modelos block source edits.

- [x] `W09.P16.S48` - Draft a modelo revision from the ledger, then modify a contributing ledger row; `src/aeat/tests/test_ledger_modelo_staleness.py`.
- [x] `W09.P16.S49` - Assert dependents are stamped stale and recalculation is triggered (no silent stale revision); `src/aeat/tests/test_ledger_modelo_staleness.py`.
- [x] `W09.P16.S50` - Assert a finalized/published modelo blocks destructive ledger edits to its source rows; `src/aeat/tests/test_ledger_modelo_staleness.py`.

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
- [x] `W10.P18.S55` - Add BucketEventType.MODELO_LEDGER_DEPENDENT_STAMPED_STALE and a work-unit stale marker mirroring the censo pattern; `src/aeat/domain/buckets/_event.py`.
- [x] `W10.P18.S56` - Tests: mutate a contributing row -> stale detected; `empty-set (non-ledger) snapshot trivially stable; `src/aeat/domain/modelos/test_ledger_filing_snapshot.py`.

### Phase `W10.P19` - Verify/file wiring and uniform modelo coverage

Capture at verify/file, surface drift, prove every-modelo uniformity.

- [x] `W10.P19.S57` - Capture the snapshot at VERIFICADO_COMPLETO and re-affirm at PRESENTADO in the calculate/verify/file flow; `src/aeat/application/modelos/`.
- [x] `W10.P19.S58` - Surface staleness in ledger/modelo status, verify, and check outputs; `src/aeat/entrypoints/cli/`.
- [x] `W10.P19.S59` - Every-modelo coverage test: ledger-fed (303/130/100) and a non-ledger modelo each carry a uniform snapshot; `filed snapshot is immutable; `src/aeat/application/modelos/test_modelo_filing_snapshot_coverage.py`.

## Wave `W11` - ECB FX provider implementation (ADR-driven)

Implement the ECB euro reference-rate provider and wire it into the CLI import path so foreign rows convert at the legally-official rate.

### Phase `W11.P20` - ECB reference-rate provider

Bundled eurofxref history + provider with date fallback and EUR-base inversion.

- [x] `W11.P20.S66` - Bundle a versioned snapshot of ECB eurofxref-hist.xml under the data tree (offline, deterministic, refreshed on release); `src/aeat/_data/fx/`.
- [x] `W11.P20.S67` - Implement EcbReferenceRateProvider(ExchangeRateProvider): parse history, get_eur_rate with most-recent-prior-working-day fallback; `strict tests (determinism, weekend fallback, EUR-base inversion direction); `src/aeat/adapters/outbound/fx/_ecb_provider.py`.
- [x] `W11.P20.S68` - Wire the normalizer into the CLI import path so foreign rows persist fx_rate+value_in_eur; `corpus-fidelity + journey assert Revolut GBP/USD convert (no UNSUPPORTED_CURRENCY); `src/aeat/application/ledger/_actions.py`.
- [x] `W11.P20.S69` - Record rate source + rate-date provenance on the conversion, dovetailing with the filing snapshot; `src/aeat/domain/transactions/_models.py`.
- [x] `W11.P20.S70` - Add an ECB-history refresh utility (re-acquire eurofxref-hist.xml on release; `runtime stays offline); `src/aeat/adapters/outbound/fx/_ecb_refresh.py`.

## Wave `W12` - CLI operator-ergonomics restructuring

Restructuring-scale CLI surfaces the personas flagged: folder import with envelope aggregation, multi-file review filtering/search, and a consolidated readiness/anomaly surface.

### Phase `W12.P21` - Import surface restructuring

Folder/multi-file import + import-batch lineage.

- [x] `W12.P21.S75` - Folder/multi-file ledger import in one invocation with envelope-aggregated rows/imported/skipped counts across files; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W12.P21.S76` - Enrich ledger track lineage to name the import-batch provenance for imported rows (not a bare '-'); `src/aeat/entrypoints/cli/_ledger.py`.

### Phase `W12.P22` - Review, filter and search surface

Classification lens + search + period-scoped JSON.

- [x] `W12.P22.S77` - review --filter classification=business|personal|gated (typed key across filter spec + query); `src/aeat/application/review/_filter.py`.
- [x] `W12.P22.S78` - Search across description/counterparty/category from the CLI (review/list search); `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W12.P22.S79` - Period-scoped JSON row list (list --period or review --filter period --format json) for building classify CSVs; `src/aeat/entrypoints/cli/_ledger.py`.

### Phase `W12.P23` - Readiness and anomaly surface

Anomaly channel + readiness dashboard + annual roll-up.

- [x] `W12.P23.S80` - Anomaly channel in check/preflight distinct from missing-fact reasons (recargo/erroneous/foreign), with severity; `src/aeat/application/ledger/_preflight.py`.
- [x] `W12.P23.S81` - Consolidated readiness dashboard (rows, pending, anomalies, ready-to-file) for sign-off; `src/aeat/application/ledger/_summary.py`.
- [x] `W12.P23.S82` - Annual roll-up / M100-readiness money totals (ingresos/gastos/net activity per year); `src/aeat/application/ledger/_summary.py`.

## Wave `W13` - Cross-profile runtime-pegged ledger domain

The cross-profile goal: a second taxpayer bucket (recargo-equivalencia retailer) with its own corpus+oracle, per-bucket isolation, switching, and the RE regime modelled end-to-end (not as an anomaly).

### Phase `W13.P24` - Second taxpayer profile + corpus

Recargo-equivalencia retailer bucket with corpus+oracle; isolation.

- [x] `W13.P24.S83` - Author a recargo-equivalencia retailer profile corpus + ground-truth oracle in a separate bucket; `src/aeat/tests/fixtures/financial/ledger-corpus-retailer/`.
- [x] `W13.P24.S84` - Cross-profile isolation test: each bucket's ledger is independent (no cross-bucket leakage); `src/aeat/entrypoints/cli/test_ledger_cross_profile.py`.

### Phase `W13.P25` - Recargo-equivalencia regime end-to-end + switching

Model RE as a real regime; operate across profiles.

- [x] `W13.P25.S85` - Model recargo equivalencia as a real regime for the retailer (IVA+RE non-deductible cost; `repercutido RE on sales), not an anomaly; `src/aeat/application/aggregation/_iva_ledger.py`.
- [x] `W13.P25.S86` - Cross-profile switching journey: operate the ledger across two profiles in one session; `src/aeat/entrypoints/cli/test_ledger_cross_profile.py`.

## Wave `W14` - UX and rendering of the profile-bound ledger at scale

Operating-scale rendering, grouping/labelling, and batch transform/amend over 1000s of rows.

### Phase `W14.P26` - Operating-scale rendering, grouping, batch transform

Render 1000s of rows; label/group; bulk amend.

- [x] `W14.P26.S87` - Render/list 1000s of rows with stable columns and honest paging/truncation (no silent cap); `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W14.P26.S88` - Grouping/labelling of transactions (label/tag/group surface) and grouped display; `src/aeat/domain/transactions/_models.py`.
- [x] `W14.P26.S89` - Batch transform/amend journey: iterative refinement (relabel/recategorize/reallocate) over hundreds of rows; `src/aeat/entrypoints/cli/test_ledger_corpus_journeys.py`.

## Wave `W15` - Google ledger export — offline/local (no network)

The no-network half of the Google export goal: serialize the bucket ledger into an XLSX / Google-Sheets-shaped workbook on local disk, roundtrip it back through import for fidelity, and attach Gmail/Drive document-link references as local row metadata — all without contacting any external service. The online counterpart (live Drive/Sheets/Gmail) is tracked separately in Wave W04.

### Phase `W15.P28` - Offline workbook export and local document links

Local, no-network deliverables: an XLSX/Sheets-shaped workbook export of the bucket ledger with an offline roundtrip-through-import fidelity gate, and Gmail/Drive document-link references attached as local ledger-row metadata (link strings recorded, never fetched).

- [x] `W15.P28.S93` - XLSX / Google-Sheets-shaped workbook export of the bucket ledger to a local file; `src/aeat/application/ledger/_workbook_export.py`.
- [x] `W15.P28.S94` - Offline roundtrip gate: exported workbook re-imports back through the ledger with row fidelity; `src/aeat/entrypoints/cli/test_ledger_workbook_export.py`.
- [x] `W15.P28.S95` - Attach Gmail/Drive document-link references as local ledger-row metadata (recorded, never fetched); `src/aeat/entrypoints/cli/_ledger.py`.

## Description


## Steps







## Parallelization


## Verification

