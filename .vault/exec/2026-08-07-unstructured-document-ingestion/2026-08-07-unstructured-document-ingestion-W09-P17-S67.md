---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:de276af12d344bdf00c128ee6526e8b1d05edadf839c0b94d119b75ff23854fc'
step_id: 'S67'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Make blocking findings block: an unresolved closure discrepancy, ambiguous identity or unresolved direction refuses confirm until each named finding carries an explicit per-finding resolution, with no bulk confirm flag, gated by refusal tests per finding class

## Scope

- `src/cadrumo/application/ledger`

## Description

- Declare two closed axes in the core: why a confirm is blocked, and how the operator settled one finding. Neither carries a waive member.
- Map every deterministic check kind to a blocking reason, and refuse the module import when a member is unmapped, so completeness is by construction rather than by diligence.
- Raise a blocker from two sources: every deterministic finding the document's own figures produced, and an ambiguous grounding outcome on a counterparty tax identifier, which raises no arithmetic finding but selects which real taxpayer the record names.
- Address each blocker by a clock-free derived id folding what the blocker is, so an id read from an earlier listing still resolves.
- Refuse the confirm when any blocker is unanswered, when a resolution names no blocker the document raises, when two resolutions answer one blocker, or when a choose-candidate picks a value that was never a recorded candidate.
- Run the gate at the top of the confirm path, before identity resolution, the attachment link and the catalogue lookup.
- Register the refusal in the error registry and set its message in all four locale catalogues.

## Outcome

A document with a finding cannot be confirmed at all until a person answers that finding by name. There is no bulk form and no partial pass: answering one of two findings still refuses, which is the shape a bulk flag would otherwise reach by a different route.

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_confirmation_gate.py -n0 -p no:cacheprovider -q
    (run jointly with the two sibling files) 30 passed in 16.27s

Mutation proofs, applied from a lane-specific plugin outside the repository so nothing under source changed:

- the gate detecting no blocker at all reddens 10 tests, first at the blocker-reason assertion;
- the gate detecting blockers but dropping the refusal reddens 9, first at the raised-refusal assertion.

Each red lands on an assertion, not on fixture setup or a production guard.

## Notes

Cache posture: `-p no:cacheprovider`, serial `-n0`; the default unit lane selects this file.

A recargo de equivalencia invoice raises a spurious arithmetic-closure finding, because the reading path does not recover the surcharge as a component of the printed total. The gate is correct and the finding is not; the reading-side fix is owned elsewhere and is deliberately not worked around here. Four sibling cases now perform the operator attestation the gate requires, per finding and with a stated reason, rather than being cleared in bulk.

The two closed axes live in the core rather than in this package, matching where the sibling reading axes are declared; that is a scope widening of one small module beyond the Step's stated path.
