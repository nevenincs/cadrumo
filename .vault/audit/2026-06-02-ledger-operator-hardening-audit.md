---
tags:
  - '#audit'
  - '#ledger-operator-hardening'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - "[[2026-06-02-ledger-operator-hardening-plan]]"
  - "[[2026-06-02-ledger-operator-hardening-adr]]"
---



# `ledger-operator-hardening` audit: `ledger operator persona testimonials and honesty review`

## Scope

Fresh-context honesty review of the ledger operator-hardening campaign at the
close of Waves W01 (corpus + oracle + fidelity gate) and W02 (operator-journey
suites). The campaign drove the real `aeat app ledger` CLI over a hand-authored
514-row operating-scale corpus (`tests/fixtures/financial/ledger-corpus/`) for
one taxpayer across 2025 H1..2026 H1, against a typed ground-truth oracle. This
audit records what the test-driven persona journeys surfaced, what was fixed in
flight, and what remains. It doubles as the persona-testimonial record: each
journey in `test_ledger_corpus_journeys.py` is an operator workflow exercised
end-to-end against the real CLI and secure storage.

## Findings

### F1 (fixed) `ledger track` crashes on every imported transaction

Pathway: `aeat app ledger track <id>` on any row that arrived via `import`.
The tracking payload model `LedgerTransactionTrackingPayload.created_event_id`
was a required `str(min_length=1)`, but imported rows carry
`created_event_id = None` (a creation bucket-event id is set only for rows
created via `ledger add`). The command raised a pydantic `ValidationError` that
the CLI boundary masked as "command input failed validation. Run `aeat config
repair`" -- a misleading recovery hint, since no config is wrong. Fixed by
making the field `str | None` (default `None`); the journey
`test_stash_remove_and_track` now locks the behaviour for imported rows.

### F2 (open, high) bulk `classify --from-csv` is O(n) catalogue re-encryptions

Pathway: `aeat app ledger classify --from-csv`. `bulk_classify_from_csv` loops
calling `update_manual_transaction_fields` per row, and each call performs a
full encrypted catalogue `load()` + `save()`. Classifying ~270 rows of the
corpus took **404 seconds** in `test_bulk_classify_from_oracle`. At the
operator-stated working scale ("1000s of transactions") this is ~25 minutes for
one bulk pass -- effectively unusable. The CI gate now classifies a bounded
12-row slice to prove the path; the scale defect is tracked as a hardening Step
(load-once / apply-all / save-once, with a perf gate of 270 rows < 30s).

### F3 (open, medium) export surface has no XLSX/Sheets path

Pathway: `aeat app ledger export --export-format`. The verb accepts only `csv`
and `jsonl`; there is no `xlsx` value. The campaign goal of a Google
Drive/Sheets export and manual review in Drive therefore needs either an XLSX
serializer or a Sheets adapter on the outbound side -- it is not reachable from
the current export surface. Tracked as a hardening Step.

### F4 (open, low / by-design) transfers are never auto-detected at import

Pathway: `aeat app ledger import`. Direction is resolved from the amount sign,
so every row lands `INCOMING` or `OUTGOING` and `NOT_YET_PROCESSED`;
`INTERNAL_TRANSFER` is only ever an operator classification. This is defensible
(the importer cannot know a debit is an own-account transfer), but it means
inter-account transfers, card top-ups, and FX exchanges silently sit as
unclassified income/expense until the operator reclassifies them -- a real risk
of double-counting in M303/M130 if skipped. Tracked as a
transfer-reclassification helper/journey Step.

### F5 (resolved during authoring) recargo equivalencia mis-modelled

The first oracle draft routed a recargo-equivalencia purchase to deductible
`soportado` IVA. RE on a purchase invoice means the buyer is under the RE
regime (a retailer); the input IVA and the surcharge are non-deductible cost.
Corrected in the oracle to a non-deductible anomaly (`iva_declarable: false`,
`anomaly: recargo_on_non_retailer_purchase`); the fidelity test
`test_recargo_equivalencia_is_not_deductible_input_iva` enforces it. Full
RE-regime modelling (a retailer charging RE on sales) is a cross-profile
follow-up.

### What is verified-complete

Corpus imports clean through the real provider (514 rows, EUR/GBP/USD); coverage
is 16/17 `IvaCategory` (the 17th, `unknown`, is a runtime sentinel) and 41/41
`SpendingCategory`. The fidelity gate (8 tests) proves import -> oracle classify
-> ECB FX normalize -> real IVA + renta-income aggregation, asserting that
intra-community/export/import categories reach M303, and that transfers,
personal, salary, rent, and interest are gated out. The journey suite (20 tests)
exercises import/dedup/dry-run, single + bulk classification, allocate + ratios,
review/filter (typed `KEY=VALUE` spec), split/merge, archive/stash/remove,
history/track, export csv/jsonl + roundtrip, preflight/check, and status -- all
green in ~1m48s.

### What remains (honest gaps)

- Live multi-agent persona testimonials (W03 P09, S23-S26): the functional
  operator workflows are covered by the durable journey suite, but qualitative
  fresh-context subagent testimonials (rendering at scale, discoverability,
  error-message quality) have not been run. Deferred, not done.
- The three hardening Steps from F2-F4 are tracked and open.
- Live Google Drive/Gmail export (W04 P11): deferred by design pending explicit
  operator go-ahead; F3 is its prerequisite.

## Recommendations

- Land F2 first: it is the single blocker to the operator-stated scale. The fix
  is a batch path that loads the catalogue once, applies every patch in memory
  reusing the single-row mutation core, and saves once, emitting events in one
  span.
- Land F3 before any live-Drive work; without an XLSX/Sheets surface the Drive
  goal cannot proceed.
- Treat F4 as an operator-education + helper concern: a `review --filter` preset
  or a guided "reclassify transfer candidates" pass before period close.
- Run the live persona testimonials (P09) once F2 lands, so the personas
  experience the hardened bulk path rather than the 404s one.

## Persona testimonials (W03 P09)

Two fresh-context persona agents drove the real CLI over the corpus end-to-end,
each landing a green persona journey test and reporting an operator testimonial.

### Persona A — autónoma, first 1T-2025 quarterly close

Test `src/aeat/entrypoints/cli/test_ledger_persona_autonoma_close.py` (green).
Findings: (1) MED no bulk/folder import — `import` is one-verb-per-CSV with a
repeated `--provider`; (2) MED `review --filter period=...` renders only a human
table, no machine output, so building a classify CSV forces a fallback to
`list --format json` + client-side date filtering; (3) MED `export` has no
`--period`, so a quarterly hand-off dumps the whole bucket; (4) LOW/known
bulk-classify is the slow path (per-row re-persist); (5) LOW `--from-csv` cannot
carry `--business-pct`, so every MIXED row (the bulk of an autónoma's
deductibles) must be classified one-by-one. Worked well: `preflight`/`check`
emit explicit per-transaction issue lists; the `MIXED` path demands
`--business-pct` rather than silently dropping it; the export envelope carries
`row_count` + `sha256`. No crashes.

### Persona B — multi-currency consultant (GBP/USD via Revolut)

Test `src/aeat/entrypoints/cli/test_ledger_persona_multicurrency.py` (8 green).
Findings (both HIGH, both silent-omission — no crash): (1) the CLI `import` path
calls `import_ledger_transactions` without a `currency_normalizer`, so every
GBP/USD row persists `fx_rate=None` / `value_in_eur=None` and will silently gate
as `UNSUPPORTED_CURRENCY` at aggregation — the conversion machinery exists
(`_apply_fx_conversion`) but is never wired, and the operator gets no import-time
signal; (2) `value_in_eur` / `fx_rate` are projected on no read surface
(`TransactionPayload` omits them), so a GBP invoice shows only its native amount
with no EUR figure and no auditable rate/source anywhere in list/review/export.
Worked well: native currency is honest end to end (GBP/USD/EUR preserved on
import and surfaced; export classification applies cleanly).

### Persona C — asesor fiscal, client review before sign-off

Test `src/aeat/entrypoints/cli/test_ledger_persona_asesor_review.py` (10 green).
Findings: (1) HIGH `check`/`preflight` are swamped by `missing_business_classification`
— a fresh import yields one issue per row (217/217 on BBVA), burying the signals
an asesor wants (the recargo anomaly, gated/erroneous rows, foreign currency);
no "anomalies except unclassified" mode and no severity ranking; (2) HIGH the
recargo-equivalencia anomaly is corpus ground-truth but there is no CLI anomaly
channel — `check`/`preflight` only emit the seven missing-fact reasons, so a
semantically-wrong-but-complete row passes clean; (3) MED `track` shows
`Created bucket event = -` for imported rows, so the import-batch lineage is not
legible from `track` alone; (4) MED no business/personal/gated lens in
`list`/`review` (filter keys limited to status/period/issue/import); (5) LOW
`preflight` requires a period while `check` aggregates all years — no single
readiness dashboard. Positive: classifying a row PERSONAL correctly drops it from
preflight and lowers the check count; the gate never silently green-lights an
incomplete business row (consistent with no-silent-under-declaration). No crashes.
Absorbed as P10 hardening Steps (anomaly channel + classification filter +
readiness dashboard).

### Persona D — year-end reviewer assembling the annual Renta (M100) picture

Test `src/aeat/entrypoints/cli/test_ledger_persona_yearend_m100.py` (9 green).
Findings: (1) HIGH no annual money roll-up / M100-readiness surface — `status`
and `check` emit counts and a boolean `ready`, never income/expense/net totals;
the full-year picture must be hand-summed from `list --format json`; (2) MED the
annual `period=2025` filter is accepted by `review` but renders a row dump, not
an aggregate; (3) MED cross-year (devengo-vs-caja) reconciliation is fully manual
— F-2025-024 (raised Dec 2025, paid Jan 2026) is date-stamped 2026, so a
`period=2025` filter under-counts 2025 accrual income and nothing links the
prior-year invoice reference to its next-year settlement; (4) LOW `check` does
expose `periods: ["2025","2026"]` (a period inventory, the closest cross-year
hint); (5) LOW no M100-shaped readiness gate. No crashes. Absorbed as a P10
hardening Step (annual roll-up / M100-readiness surface + devengo-vs-caja view).

All four personas landed green tests and zero new crashes; every HIGH finding is
a silent-omission or missing-surface gap, now tracked. The multicurrency import
defect is the most material and is resolved at the decision level by the sibling
`[[2026-06-02-ledger-fx-conversion-adr]]` (ECB euro reference rates as the
canonical, legally-official FX source), with implementation tracked in plan wave
W11.

Both multicurrency findings are absorbed as hardening Steps in this campaign's plan (P10):
import-time normalizer wiring and payload FX projection (both HIGH), plus the
`export --period` / period-scoped JSON affordances from Persona A. The
multicurrency HIGH findings are material to the project's multicurrency goal:
the corpus's foreign income will not reach M303/M130 through the CLI path until
the import normalizer is wired.

## Implementation outcomes (post-testimonial)

- **Multicurrency HIGH #1 RESOLVED.** The ECB euro reference-rate provider
  (`EcbReferenceRateProvider` over a bundled `eurofxref` snapshot, with
  most-recent-prior-working-day fallback and EUR-base inversion) is implemented
  and wired into the CLI import composition root, grounded by the
  `[[2026-06-02-ledger-fx-conversion-adr]]`. Imported GBP/USD rows now persist
  `fx_rate` + `value_in_eur` instead of silently gating at aggregation. Covered
  by the fx adapter suite (10 tests) + a CLI import-conversion test, plus a
  refresh utility for offline snapshot updates. Plan wave W11.
- **New latent bug found and fixed (F6).** Wiring the normalizer surfaced that
  `_apply_fx_conversion` returned the *signed* `eur_amount`, which violates
  `Transaction.value_in_eur`'s non-negative invariant — so importing any
  negative-amount foreign row would have crashed the moment a normalizer was
  supplied. Fixed to store the magnitude (sign carried by `raw.amount` +
  direction). This had never fired only because the CLI never wired a normalizer.
- Multicurrency HIGH #2 (project `value_in_eur`/`fx_rate` on read surfaces) and
  the asesor/year-end findings remain tracked P10/W11 Steps; #2 is now meaningful
  to land since import populates the values.

## Codification candidates

- **Source:** F1 (`ledger track` crashed on imported rows).
  **Rule slug:** `import-only-fields-are-nullable-in-payloads`.
  **Rule:** A CLI/application payload field that is only populated for
  manually-created rows (creation event id, manual actor, source command) MUST
  be typed nullable, because the same payload renders imported rows that lack it.

- **Source:** the raw-plus-oracle corpus design (already named in the ADR).
  **Rule slug:** `ledger-corpus-is-raw-plus-oracle`.
  **Rule:** Ledger end-to-end fixtures ship as raw bank-export files plus a
  separate typed ground-truth manifest; never encode tax facts (IVA category,
  classification, casilla) inline in the import CSV.

Deferred to codify until the corresponding fix lands: F2 (bulk-write batching
discipline) is better promoted as a rule once the load-once/save-once pattern is
implemented and proven, so the rule can cite the canonical batch helper.


