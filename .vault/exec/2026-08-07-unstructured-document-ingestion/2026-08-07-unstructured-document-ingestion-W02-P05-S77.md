---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:9045f6c278da46cbf0552ba4d6c6c068ba0cb3af8c632135685b046fe15ab079'
step_id: 'S77'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Declare the field-form contract once and compile it into both the extraction prompt and the grounding validators (a rate as a bare number, amounts preserving the printed decimal separator, dates exactly as printed), resolving the printed-percent mismatch, gated by a contract-parity test proving prompt guidance and validator vocabulary derive from one declaration

## Scope

- `src/cadrumo/llm`

## Description

- Confirm the single field-form declaration is live and both derivations bind to
  it: one tuple of typed contract rows, each carrying the form the value must
  arrive in, the concept it means and the micro-guidance line the prompt renders.
- Extend the declaration with the two withholding fields, exercising the
  single-declaration property rather than asserting it: adding the rows alone
  reddened the parity gate, the fully-populated grounder round and both anchor
  fixtures until the response schema, the anchor mirror and the grounding
  dispatch had gained them too.
- Ground the withholding rate through the existing percentage form and the
  withheld amount through the monetary form, so the printed-percent resolution
  covers them with no new grounding branch.
- Populate the end-to-end Spanish fixture with a real withheld invoice, correcting
  its arithmetic to base plus cuota less retencion.

## Outcome

The form vocabulary is declared once and consumed twice, and the parity gate
proves it in both directions: the declaration covers the response schema exactly,
every declared form has exactly one grounding validator, and the grounder grounds
exactly the declared fields. The printed-percent mismatch stays resolved for the
new fields for free, because a rate is a form rather than a field: a document
printing a withholding as `-15%` yields the value `15` while its anchor keeps
`-15%` verbatim, so the distinction anti-fabrication depends on survives.

That the addition of two fields could not be made without the gate firing four
times is the evidence the declaration is load-bearing rather than decorative.

## Verification

    pytest src/cadrumo/llm/tests/test_invoice_field_contract.py src/cadrumo/llm/tests/test_invoice_prompt_cache_binding.py src/cadrumo/llm/tests/test_invoice_field_anchors.py -n0 -p no:randomly -q
    90 passed in 29.94s

Run sequentially on a cold interpreter against an isolated export of the tree,
because a concurrent lane's in-flight consent work leaves the working copy of the
llm package unimportable. Model-free and network-free throughout: no transport is
constructed anywhere in these gates.

Before the response schema and grounding dispatch were extended, the same
selection reported the parity gate biting on the incompleteness:

    5 failed, 85 passed in 38.69s

## Notes

The wider suites show 31 failures both before and after the change, an identical
set with zero delta, measured as a set difference against a baseline captured
from a pristine export of the same commit. Those failures belong to a separate
lane rewriting tests that assert a deterministic text path a ruling removed.
