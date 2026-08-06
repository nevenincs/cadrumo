---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:4c4665420e678b443f1094bf3fa8a06ab421de628d914f12f08190b6377cccd0'
step_id: 'S49'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace ledger-invoice-decomposition with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S49 and 2026-08-05-ledger-invoice-decomposition-plan placeholders are machine-filled by
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
     The Drive one accumulative invoice life through Modelo 303 and 390 and through Modelo 130 and 100 across several periods, asserting the same operation lands in one period on both the quarterly and annual sides and ## Scope

- `src/cadrumo/application/aggregation/tests` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Drive one accumulative invoice life through Modelo 303 and 390 and through Modelo 130 and 100 across several periods, asserting the same operation lands in one period on both the quarterly and annual sides

## Scope

- `src/cadrumo/application/aggregation/tests`

## Description

- Added `test_invoice_accumulative_cross_modelo_periods.py`: for each of four
  quarters, persists one issued invoice bidirectionally linked to one ledger
  transaction, drives the real `calculate_modelo_revision_from_bucket_aggregation`
  action for Modelo 303 and Modelo 130 for that quarter, files each revision
  through `persist_filed_revision_observation`, then calculates the Modelo 390
  and Modelo 100 annual revisions from the same persisted state.
- Asserted two layers per modelo pair:
  - Transport invariants (matching the two existing e2e verticals'
    established style): each quarter's engine-computed casilla equals the
    stored transaction/invoice field value, never a re-derived figure; the
    annual fold equals the sum of the four engine-computed quarterly values;
    the four quarterly values are distinct and (for M130) strictly positive.
  - An independent anti-duplication check the existing verticals do not
    perform: the annual M390/M100 totals are also compared against the sum of
    the invoices' own declared base/IVA -- data recorded before any
    calculation ran, never re-read from an engine output. A defect that
    duplicated one invoice identically across two quarters would still
    satisfy "annual == sum(quarters)" (both sides double) but would fail this
    independent check.

## Outcome

One real, persisted `Invoice` -- not a bare ledger transaction, per the two
existing e2e verticals -- now drives both the IVA family (303 quarterly ->
390 annual) and the income family (130 quarterly -> 100 annual) from the same
linked transaction, and the test proves neither family lets an operation leak
into, or duplicate across, more than one period.

The M303/M130 quarterly calculate + file, and the M390/M100 annual calculate,
all run against the real registry authority, the real encrypted secure-object
store, and the real calculation engine; no revision id is hand-picked. Zero
expense/purchase transactions are used, keeping the M130/M100 formula chain to
its clean incremental pago-fraccionado path (the same device the M130/M100
precedent uses via a high prior-year net-income seed to zero the minoración).

## Verification

    uv run --no-sync pytest src/cadrumo/application/aggregation/tests/test_invoice_accumulative_cross_modelo_periods.py -q --no-header -n 0
    1 passed in 12.62s

    uv run --no-sync pytest src/cadrumo/application/aggregation src/cadrumo/application/modelo -n auto -q --no-header
    2176 passed, 6 warnings in 145.49s (0:02:25)
    (the 6 warnings are SerialTestsHeldWarning for two unrelated pre-existing
    benchmark tests correctly held out of a parallel run, not failures)

    uv run --no-sync ruff check src/cadrumo/application/aggregation/tests/test_invoice_accumulative_cross_modelo_periods.py
    All checks passed!

    uv run --no-sync ty check src/cadrumo/application/aggregation/tests/test_invoice_accumulative_cross_modelo_periods.py
    All checks passed!

Mutation proof: the first mutation attempt (disabling the per-candidate period
gate in the unrelated sibling function `aggregate_iva_ledger_candidates`, and
separately widening only the repository partition window) each independently
left the test green -- the repository-level date-index partition and the real
per-transaction gate in `_classify_iva_transaction` are two independent,
redundant defences, so disabling only one leaves the other still correct.
Combining both mutations (widen `aggregate_iva_ledger_observations_from_repositories`'s
partition window to the full filing year AND disable the real period gate at
`_classify_iva_transaction`'s `resolved_period.contains(operation_date)`
check) reddened the test as expected: 1T's cuota-devengada-total read
4620.00 (the full annual total) instead of 1050.00 (its own quarter).
Restored `_iva_ledger.py` byte-for-byte via `cp` from a pre-mutation backup;
SHA-256 matched the pre-mutation value exactly
(`4b5701b31741d687c1fc5c351b392252a0711370b886f7857cc3b22564fe2017`) and
`git diff` against HEAD showed zero changes. Re-ran the test green afterward.

## Notes

- The two false-negative mutation attempts (see Verification) are a real
  finding about the codebase, not a flaw in the probe: the IVA ledger period
  gate is enforced TWICE independently (a plaintext-date-index repository
  partition, then a per-transaction `resolved_period.contains()` classify
  check), so a single-point mutation of either layer alone is invisible to
  any test relying on the other layer still being correct. This is a
  legitimate defence-in-depth design, not a defect; recorded here only
  because it cost three mutation rounds to find the layer that actually
  needed both defences disabled together.
- No dependency on the invoice `operation_date` field (added by a peer agent
  earlier in this campaign) was needed: this Step's invoices keep
  `operation_date` unset, so period attribution runs entirely on the linked
  transaction's own ledger date -- the already-wired path. Threading the
  invoice devengo date into IVA period attribution itself remains separate,
  later work per `_invoice_devengo.py`'s own docstring, and is out of this
  Step's scope.
