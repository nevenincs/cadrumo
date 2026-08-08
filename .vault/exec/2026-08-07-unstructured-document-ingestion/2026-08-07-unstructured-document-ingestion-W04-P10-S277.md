---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:ec37414f1f991ae3b80cd0b1edc7d479974458b5fe2aa0d5c376d5fab1509c28'
step_id: 'S277'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Description

- Add one selection authority that turns a field selection into contracts, validated against the declaration.
- Thread the selected contracts through all three blocks that enumerate fields, so none can ask for a different set.
- Accept the selection on both entry points, on identical terms.
- Preserve declaration order whatever order a caller passes.
- Refuse an unknown name and an empty selection, naming the accepted set.

## Outcome

The compiler emitted every declared field contract on every call: the field-line helper took no arguments and neither entry point accepted a selection. The fewer-fields arm of the measurement it blocks was not measured badly, it was inexpressible.

Measured before and after, counted off the EMITTED text rather than the argument:

    full, no selection      18 contracts, 8598 chars, fingerprint 94acbce47cf0
    complete selection      byte-identical to the above
    subset of 3             3 contracts, 4427 chars
    reversed order          identical bytes to forward order
    empty / unknown name    refused, accepted set named
    partly valid selection  refused whole, not silently shortened

The refusal is the substantive half. A dropped name still renders, just shorter, and a measurement taken against a prompt missing a contract nobody noticed is worse than no measurement because it carries the authority of a number. An empty selection refuses on the same terms the period path fails closed on an empty rate set: a prompt asking for nothing is not a smaller prompt.

Declaration order is preserved rather than the caller's argument order, so two arms passing one set differently ordered cannot differ by argument order alone -- a difference nobody would think to control for.

One authority rather than three, because the three blocks that enumerate fields would otherwise be free to disagree: a block emitting a different subset from its siblings would ask the model for a key the skeleton never lists, or list a key the field block never explains.

## Verification

    uv run --no-sync pytest src/cadrumo/llm/tests/test_invoice_prompt_field_subset.py -n0 -q -m unit
    13 passed in 6.10s

    uv run --no-sync pytest src/cadrumo/llm -n0 -q -m unit
    433 tests ran; 4 were DESELECTED by -m 'unit' and never executed.
    433 passed, 4 deselected in 220.57s (0:03:40)

    uv run --no-sync ruff check src/cadrumo/llm/_invoice_extraction_prompt.py --output-format=concise
    All checks passed!

Comparability is asserted BYTE-for-byte against output captured before the first edit, not structurally. A structural check passes on a prompt whose field ordering moved, which is exactly the change that would make two measurements incomparable while looking equivalent. The unselected fingerprint is unchanged.

The mutation was applied from outside the repository through a pytest plugin, so no mutation window existed under the source tree for a sweep to take. It made the selection inert -- accepted and then ignored -- and proved the window open by rendering a two-field ask and observing eighteen contracts emitted before declaring itself applied. Seven cases red: every subset count and every refusal. Six stayed green, correctly: byte-identity, the full-set control, order-independence, entry-point agreement and the empty-rate refusal are all insensitive to whether a subset is honoured, which is what makes the seven attributable.

## Notes

The fail-closed behaviour was checked in both arms and is intact: a period with no in-force rates refuses identically with and without a selection, so a subset is not a route around it.

The briefed example of that behaviour no longer reproduces. 2012 was cited as failing closed on an empty rate set; at HEAD it renders, with and without a selection, because the rate table now carries a 2012 record. The same backdating correction reddened a sibling row's coverage assumptions. The guard itself was confirmed against a genuinely unpriced year rather than assumed from the cited one, and the boundary now sits below 2005.

The module carries mixed line endings, which defeated three scripted edits that matched on newline-bearing patterns. Detecting the dominant ending before matching resolved it; the earlier failures wrote nothing, because each script asserted before writing.
