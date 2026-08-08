---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:fdebaa6ddcbddffd23bb85c41bf000297048ad28097a72a1b0fa639199cab846'
step_id: 'S192'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Description

- Add a roundtrip fixture whose acquirer is established in Spain and VAT-identified in France, so the two facts diverge and a country-derived reload cannot pass.
- Push it through the real encrypted invoice repository and assert strict equality across the cycle.
- Add the anti-tautology proof: delete the persisted key from the encrypted envelope, reload, and assert the result no longer compares equal.

## Outcome

The new identification field survives the real encrypted persistence boundary
populated non-default, and a save-drops-field regression on it is detectable.

The fixture's divergence is what makes the roundtrip worth anything. Had the
acquirer been French-established AND French-identified, a boundary that quietly
re-derived the identification from the address on load would have returned the
same value and the test would have passed while proving nothing. It asserts
after reload that the address still reads Spain while the identification reads
France.

Writing this fixture is what surfaced the third conflated site: the invoice
record refused to construct a Spanish-established, French-identified acquirer at
all, because its own intra-community guard read the address. That guard was
re-keyed under the sibling Step before this proof could run.

## Verification

    uv run --no-sync pytest src/cadrumo/domain/invoices src/cadrumo/application/aggregation -m unit -n0 -q --ignore=src/cadrumo/domain/invoices/tests/test_rate_coverage_versus_legality.py
    1 failed, 1039 passed, 11 deselected in 123.00s (0:02:03)

The single failure belongs to a concurrent rate-table lane, not to this
boundary. Both new roundtrip tests are in the passing set.

## Notes

The proof asserts inequality after the deletion rather than a refusal. The
field is legitimately nullable, so its absence is a valid shape and the model
cannot raise on it; inequality is the honest tooth here, and it does bite —
a silent re-default is exactly what it catches.

Only the invoice boundary is covered. The transaction record carries the same
new field but persists through a different repository, and no equivalent
divergent-fact roundtrip exists for it yet.
