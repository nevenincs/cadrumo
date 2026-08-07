---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:afb301521ab8b191897a9ad14b26a16ccb380ead881608630b78cd1005833609'
step_id: 'S26'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

# Widen the confirm-boundary override set from the extraction draft's field set to the writer's, adding retencion, recargo, invoice-class, series, rectifies-invoice-number, iva-category, operation-date and the missing iva-amount, so an operator confirming a rectificativa or a retencion-bearing invoice from evidence need not abandon the evidence path

## Scope

- `src/cadrumo/application/ledger/_evidence_draft.py`

## Description

- Confirmed the shared file carried no peer WIP before the first edit, since this module is the declared seam with the sibling campaign.
- Widened the confirm function's parameter list to the writer's field set.
- Wired the printed-cuota override as evidence rather than as an arbitrary number.
- Added a rate-slot helper that refuses an unrecognised percentage instead of degrading it.
- Touched no draft model field, which is the other lane's.

## Outcome

**Confirming from evidence now reaches the same axes as direct entry.** Before this the boundary accepted only the extraction draft's fields, so an operator confirming a rectificativa or a retención-bearing invoice from evidence had to abandon the evidence path and re-key the record — losing the attachment link that the confirm path exists to create. The evidence path was usable only for the simplest invoices, which is the opposite of what an evidence path is for.

**The `iva_amount` override is the one the Step singled out, and it is wired as EVIDENCE rather than as a number.** A cuota printed on a document outranks a recomputed one, so supplying it makes the persisted line carry that exact figure instead of base times rate. That is how a document whose printed cuota differs by a cent from the arithmetic gets recorded as it was issued rather than as it 'should' have been.

Crucially the line invariants still apply, so a cuota the base and rate cannot support **refuses**. The override is a way to record what the document says, not a way to bypass the arithmetic.

**The rate-slot helper refuses rather than degrades.** An unrecognised percentage raises instead of falling to the exempt slot — which would mint a zero-cuota invoice against a document that plainly printed a cuota, the silent under-declaration this campaign keeps finding in different clothes. It reads the writer's own accepted-slot table rather than restating it, so the confirm boundary and the direct writer cannot drift about which rates exist.

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_confirm_cli.py -q --no-header
    578 passed in 39.82s

    uv run --no-sync ruff check .../_evidence_draft.py .../test_evidence_draft_printed_total.py
    All checks passed!

The cross-lane boundary was respected and checked: this Step changes the confirm FUNCTION's parameter list and adds no field to the draft model, which the sibling campaign owns. The file was confirmed identical to `HEAD` before the first edit.

## Notes
