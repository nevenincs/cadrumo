---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:a81690dd1437d2370500bc06173aa58d009b7c95ac85f694c1ed769d15b52ef3'
step_id: 'S200'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Outcome

`UNSUPPORTED_IVA_RATE` is mapped in both preflight mappings at HEAD. Verified by
content, not by report: `git show HEAD:src/cadrumo/application/ledger/_preflight.py
| grep -c UNSUPPORTED_IVA_RATE` returns 2, one per mapping.

## What the defect was

`_preflight_reason_for_iva_issue` and `_preflight_detail_for_iva_issue` are bare
`{...}[reason]` dict lookups — total by construction, so an unmapped member raises
`KeyError` rather than degrading. `UNSUPPORTED_IVA_RATE` was added to
`IvaLedgerAggregationIssueReason` by commit `360383e2` ("stop telling a taxpayer
their rate is wrong when their year is unsupported") and reached neither mapping.

A transaction whose IVA rate belongs to an unsupported filing year therefore
crashed the preflight instead of surfacing an operator-facing issue. The
aggregation layer reported the condition correctly and the preflight layer could
not receive it — the campaign's built-and-unreached shape inverted.

## How it was found, and what nearly hid it

A second defect masked it completely. `_preflight.py:530` still named
`MISSING_COUNTERPARTY_EU_MEMBER_STATE` after a peer lane renamed that member, so
six preflight tests failed with `AttributeError` before any `KeyError` could
occur. Two lanes independently triaged the red and reached **different** causes,
each reasoning from the enum's contents rather than from a traceback. Both
defects were visible in the enum; only one was visible in the failure output.

The distinguishing measurement was one command:

    pytest -k preflight -m unit -n0 | grep -E "^(E |FAILED)"

All six failures carried one signature, and it was not this one. The mapping gap
was real, latent, and would have surfaced only once the first defect cleared.

## Verification

    pytest src/cadrumo/application/ledger/tests -n0 -m unit -k preflight
    41 passed, 1076 deselected

That is the `unit` lane only. The production change reached HEAD via sweeper
commit `24267e3167` while the authoring lane was still working.

## Carried forward

The structural half is `W09.P17.S201`: making both mappings total **by
construction** so a new enum member cannot ship unmapped. Two lanes renamed
members of this one enum inside a day, which is the argument for the guard —
a total mapping keyed on a shared enum is a contention point between every lane
that touches it.
