---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:409f315ddb1bf78d3de9b0199807b0dee27b9181713a5073f3b852a56ca0e46b'
step_id: 'S27'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Project rows deterministically under a confirmed mapping so the model never touches a cell value, gated by a property test asserting projected values byte-equal their source cells

## Scope

- `src/cadrumo/adapters/inbound/financial`

## Description

- Add `_tabular_projection.py`: a positional column-role mapping, the copy step,
  and the reports for unmapped and contested columns.
- Assert the copy as byte equality over the nine bundled exports and over an
  adversarial cell space rotated through every column position.
- Export the projection surface through the providers and financial facades.

## Outcome

Projection copies each cell into its role and does nothing else: no stripping,
no separator rewriting, no date parsing, no type coercion. The mapping arrives
as data — one role per column, positional. The semantic mapper of the sibling
Step has since bound itself to that seam, and this module needed no change for
it, which is the separation working as intended rather than a claim about it.

The property is asserted by comparing `.encode("utf-8")` on **both** sides, not
equality after normalization. That is deliberate and load-bearing: a
semantic-equality-after-normalisation assertion cannot satisfy this test, because
the comparison never normalises either operand. Equality-after-normalization would be satisfied by a projection
that rewrote a Spanish printed amount on the way through, which is precisely the
defect the guarantee exists to prevent: at the far end, a silently normalized
value is indistinguishable from an invented one.

A column whose meaning was not established is reported and copied nowhere; the
file is never refused for carrying one. A role claimed by two columns — a
debit/credit split is the real case — is reported with both claimants rather
than resolved to whichever came first.

Positional addressing rather than header text, because real exports carry blank
and duplicated header cells and position is the only identifier that addresses
exactly one column.

## Verification

The lane's own tests, with the touched detection tests alongside them:

    uv run --no-sync pytest src/cadrumo/adapters/inbound/financial/providers/tests/test_tabular_dialect.py src/cadrumo/adapters/inbound/financial/providers/tests/test_tabular_projection.py src/cadrumo/adapters/inbound/financial/providers/tests/test_mapped_tabular_fallback.py src/cadrumo/adapters/inbound/financial/providers/tests/test_detection_ordered.py -p no:randomly -n0
    51 passed in 3.52s

Collection counts read from the log on disk, confirming nothing was deselected:

    51 tests collected in 1.15s

Two mutations proved the byte-equality property bites, both applied from a
throwaway plugin outside the repository so no tracked file changed. Making the
copy normalize a European decimal reddened thirteen tests, among them the
byte-equality assertion for every one of the nine bundled exports. Making the
copy strip surrounding whitespace — the subtler defect, invisible to a semantic
comparison — reddened three. Both were restored and the suite re-run green.

## Notes

The adversarial cell space is written out as a real delimited file and read back
through the production normalizer rather than assembled as a table in memory, so
the property is exercised end to end. Each shape is rotated through every column
position, so no assertion depends on a shape sitting in a particular column.

A companion test pins the projected cell count and the presence of the shapes
that matter most. Without it, a projection emitting no cells at all would satisfy
"every projected value is byte-equal to its source" vacuously.

The source of this Step was committed by a concurrent tree-wide peer sweep rather
than by this Step's own commit. HEAD content was verified to match the working
tree for every path before proceeding.
