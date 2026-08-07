---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:b668772d446f2a85501d9a4d57171d420d4601919d7e4edd4aa5f01bfc03edd3'
step_id: 'S21'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W05.P07.S21

## Outcome

Diagnosed, and the direction is the right one: the four fields are carried by the model, not dropped from the test. No data-loss regression was papered over as test staleness.

## The question the Step insists on

An `extra="forbid"` failure naming `recargo_amount`, `lines`, `iva_breakdown` and `iva_category` has two possible fixes, and they are opposites:

- the payload model lost fields it should carry, and the test was right — restore the model;
- the payload never carried them, and the test asserted a shape that never shipped — fix the test.

Choosing wrong in the second direction is harmless; choosing wrong in the first silently drops recargo and the per-rate IVA breakdown out of an operator-facing extract while the suite goes green.

## What the evidence says

`application/ledger/_evidence_draft.py` carries all of them as first-class fields today, and populates them from the parsed document rather than defaulting:

- `recargo_amount: Decimal | None` on the draft (`:300`), on the per-rate breakdown row (`:252`) and on the parsed record (`:224`)
- `iva_breakdown: tuple[InvoiceDraftRateBreakdown, ...]` (`:302`)
- both assigned from the parse at `:538` and `:551`

So the data reaches the draft. The regression was resolved by keeping the fields, which is the direction that does not lose a recargo component — the same component `iva-cuota-devengada-includes-recargo-equivalencia` and the `CounterpartObservation` finding both turn on.

## Current state

`test_ledger_evidence_extract_cli.py` — **6 passed**. The `extra="forbid"` failure does not reproduce.

## Honest limit on this diagnosis

The `git log -p` search for removed assertions came back empty, but that is weak evidence rather than proof: this file was swept by two broad "land the in-flight source work" commits whose diffs are large, and an assertion removed inside one of those would not surface in a targeted grep. The strong evidence is the positive one — the fields exist and are populated on the model the CLI serialises — and that is what the conclusion rests on, not the absence of a deletion in the log.
