---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:469e9fff3f52454abb77dda1dd1f162cc11c829b443b10c53638ac9106e163ab'
step_id: 'S273'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Give the operator a verb that reads back the identification state

## Scope

- `src/cadrumo/entrypoints/cli`

## Description

- Add the identification state and its provenance to the show payload.
- Read them from the resolution rather than from the stored record.
- Gate the read-back, its absence control, and the constraint the work surfaced.

## Outcome

`confirm` accepted `--identification-state` while `show` emitted the territorial side alone, so an operator could write a fact and never read it back. A write-only value at the operator boundary is worse than an absent one: it cannot be reviewed, corrected with confidence, or told apart from a value nobody supplied.

Both values are read from the resolution rather than the repository, so what an operator is shown and what a later document consumes cannot drift. The resolver withholds a fact the evidence contradicts, and a payload read straight from the store would show a value no document will use.

`confirmed` deliberately stays the TERRITORIAL answer rather than becoming a summary of both, because it is what the establishment rung fires on and what callers branch on. A record carrying only an identification reports it beside `confirmed = false`, which is the honest shape.

## Verification

    show CLI + counterparty CLI (unit or integration, -n0):   18 passed of 18 collected
    JSON schema conformance:                                 333 passed of 333 collected

Post-change semantic search over the identification surface returns no prose claiming the value is unreadable.

## Notes

The row's scope names `src/cadrumo/entrypoints/cli/_ledger_evidence`; the verb and its payload are in `_ledger_counterparty_cli.py` and `_ledger_counterparty_payloads.py`. Worked in the correct place.

A constraint surfaced that the row did not anticipate, and it is asserted rather than left to be met by an operator: `--scope` is required while `--identification-state` is optional, so somebody who knows which State VAT-identifies a counterparty and NOT where it is established cannot record the half they know. That is a real asymmetry on an axis the fifth amendment split precisely because the two facts are independent. My first draft of the gate assumed the two were independently settable, the CLI refused with exit 2, and the test now asserts the refusal. Making the territory optional is a behaviour change and belongs in its own row.

Two edit passes aborted on their own assertions before writing, both because a peer had rewritten the anchors since the file was read: a docstring paragraph, and an import that already carried the symbol being added. Nothing was written in either case, which is why the anchors assert rather than replace-if-present.
