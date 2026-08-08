---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:d2276dff02a4662c213ccecf18a65db3265dac3c9344443e4f85f031e467e1ba'
step_id: 'S209'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Re-anchor the rate coverage premise, and close the vacuous tier guard

## Scope

- `src/cadrumo`

## Description

- Measure the true per-tier reach before changing anything: the general and reducido records now run from September 2012, the super-reducido ones only from 2024, and the zero-tier windows fall strictly inside the general one.
- Re-anchor the lawful-but-uncovered date onto the super-reducido tier, the only tier that still has a coverage gap, and name the constant for the tier it belongs to.
- Replace the two general and reducido refusal cases with an assertion that their gap is CLOSED, pinning the rate correction rather than deleting the cases.
- Add an anchor asserting the super-reducido tier genuinely does not reach the probe date, so a later backdating reds with a message naming the premise instead of the rate.
- Correct the operator-facing refusal message, which claimed the registry carried no rates for Spain on a date where it carries two tiers, to name the tier whose record is missing; correct the comment beside it that still described the table as having no record before 2024.
- Replace the vacuous tier-narrowing guard with a containment anchor that walks every day from 2010 to 2026 and asserts no date separates the two readings, carrying the instruction to restore a behavioural probe when one does.
- Sweep the remaining places a refusal describes the table's reach: the ledger detail that called it a current-rates table, the enum member comment that scoped the condition to every record rather than to the positive tiers, and the invoice docstring that framed the question as whether the table reaches a date at all.
- Pin the ledger wording in the gate that already reads that message, so the sentence and the data it describes are tied together.

## Outcome

The tier-narrowing guard could not be repaired by re-anchoring its span, and saying so is the substantive finding. After the general and reducido windows were corrected to 2012 the zero-tier windows sit strictly inside them, so no date in 2010 to 2026 separates "any tier covers" from "a positive tier covers" — measured exhaustively by day, not sampled. A probe-based guard is therefore unwritable against this data whatever span it walks. The scoping is still correct and still load-bearing, so the guard is now an equality against a locally spelled-out tier tuple plus a containment anchor that reds the day the separation becomes observable again.

## Verification

    uv run --no-sync pytest src/cadrumo/domain/invoices/tests src/cadrumo/domain/iva/tests -n0 -q -m unit
    904 passed in 40.30s

    uv run --no-sync pytest src/cadrumo/domain/invoices/tests/test_rate_coverage_versus_legality.py -n0 -q
    10 passed in 13.81s

    uv run --no-sync ruff check src/cadrumo/domain/invoices
    All checks passed!

    uv run --no-sync ty check src/cadrumo/domain/invoices
    All checks passed!

    uv run --no-sync pytest src/cadrumo/application/aggregation/tests src/cadrumo/domain/invoices/tests src/cadrumo/domain/iva/tests -n0 -q -m "(unit or integration) and not external_tool and not os_keychain"
    1749 passed in 286.83s (0:04:46)

Every new anchor was proved to bite by mutating the rate table from outside the repository rather than by editing a tracked file, each mutation reporting the number of times the mutated table was read so an ineffective rebinding could not read as a pass. Backdating the super-reducido records to 2015 makes the uncovered-date anchor red. Re-truncating the general records to 2024 makes the gap-closed test red. Giving the zero tier a 2005 window outside every positive one makes the containment anchor red, naming both separating dates. The tier-naming assertion was checked against the message text as it stood before this change, where both of its clauses fail.

## Notes

The extent sweep found three sites and no more; a search for the phrasings that assert how far the table reaches now returns nothing outside the tests that pin them. The new ledger assertion was proved to bite against the message as it stood before the sweep, and the same probe confirmed both clauses the existing gate already read survive the rewording, so that gate was not weakened to accommodate this one.

The four failures reported against this premise earlier are all resolved: three were re-anchored here, and the fourth, in the ledger aggregation suite, was closed by a peer in the interval.

Both files landed inside a large sweeper commit carrying many other agents' work rather than a commit composed here.
