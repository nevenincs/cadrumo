---
tags:
  - '#audit'
  - '#ledger-operator-hardening'
date: '2026-06-02'
related:
  - "[[2026-06-02-ledger-operator-hardening-plan]]"
  - "[[2026-06-02-ledger-operator-hardening-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace ledger-operator-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar]]'.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

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

<!-- Findings that satisfy the three durability criteria
(cross-session, constraint-shaped, project-bound) and should be
promoted into project-shared rules under `.vaultspec/rules/rules/`
(the directory the CLI's `vaultspec-core spec rules add` writes to today; the
planned `--scope project` flag will move authored rules under
`.vaultspec/rules/rules/project/`).

Each candidate names the finding it derives from, the proposed
rule slug (kebab-case, naming the constraint's subject not the
failure), and a one-sentence statement of the rule.

Most audits produce zero codification candidates. Some produce one.
Only the rare framework-wide-pattern audit produces several. If
none of the findings above meet the bar, state that explicitly and
move on -- an empty Codification candidates section is a positive
signal, not a failure. -->

<!-- Example:

- **Source:** finding S04 (destructive verbs lack preview).
  **Rule slug:** `destructive-verbs-need-dry-run`.
  **Rule:** Every CLI verb that writes or removes state must
  accept `--dry-run` and emit a usable preview before applying.

-->
