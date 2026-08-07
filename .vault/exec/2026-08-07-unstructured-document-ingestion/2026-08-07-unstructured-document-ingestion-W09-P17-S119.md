---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:5545d3fbcadbcbcde7d2c90e5db7c1af8f94c12710d90b79223424fb2677a025'
step_id: 'S119'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Context

Reconstructed by the coordinator from the implementing lane's report, verified
against HEAD, rather than authored by the implementer. The lane was near the end
of its budget and chose to hand over an accurate account rather than write a
record it would have rushed. Every figure below was re-measured before it was
written.

The row exists because a preceding Step turned on deterministic checks for the
structured e-invoice path, which had never run them. That created a class of
record on disk that predates the checks, and nothing distinguished it from one
minted under the full set.

## What changed

The checks became data. One tuple, `DETERMINISTIC_CHECKS`, is executed by
`deterministic_findings` and enumerated by `deterministic_check_names` — one
declaration, two uses. The confirmation record gained a `checks_run` field
populated from that enumeration.

The row named the trap it had to avoid: a hand-written list of check names would
have been a second declaration of the set, drifting from the executed list the
moment a check was added. That is the same defect the preceding Step removed one
layer down, and it would have returned inside the record that exists to attest
the set.

## The paired proof

A case adds a check to the declaration and asserts the stamp follows with no
second place updated. A second case asserts the added check also RUNS.

The second is the load-bearing one and is easy to omit. A stamp derived from a
list that nothing executes would truthfully name checks that never ran — worse
than the gap it replaces, because an absent field makes no claim while a
populated one reads as evidence.

## Two decisions, taken deliberately

**The stamp keys on the check, not on its findings.** The closure check raises
three discrepancy kinds, so naming it for one of them would describe a third of
what it does, and an auditor asking whether the breakdown check ran would find no
such name and conclude it did not. A case pins `closure_identities` present and
`arithmetic_closure` absent.

**An absent stamp means no claim.** `None` is a third state rather than shorthand
for empty: an empty tuple means the set was recorded and was empty. Reading a
pre-field record as "no check ran" lies toward alarm; reading it as "every
current check ran" lies toward assurance. Both readings are refused in the
field's own docstring, where the next reader meets them rather than having to
find this record.

No backfill. Reconstructing the set for records already on disk would invent
exactly the claim the field exists to prevent, and the pre-release regime means
there is no released data to migrate.

## The decision nobody asked for, which is the sharpest one

The stamp is deliberately NOT folded into `derive_confirmation_id`.

The id folds the outcome so that a retry matches an existing record. Folding the
check set in would re-address every existing confirmation the moment the product
grew a check, so two records of the same confirmation would stop matching for a
reason having nothing to do with the confirmation. That is the idempotency guard
failing silently.

Including it would have looked like the thorough choice. A case asserts the id
stays stable across a check being added while `checks_run` moves.

## Verification

    uv run --no-sync python -m pytest src/cadrumo/application/ledger/tests/ -n0 -p no:cacheprovider -q -m unit
    1 failed, 860 passed, 21 deselected in 215.86s

Six of those are the new gate. Landed at `bdc00f3a7c`, four files, deletion count
checked before commit — eight, all lines the change replaces.

The single failure is not this change's. It fails against the working tree and
PASSES at HEAD, which is normally the signature of a regression the runner
caused. Here it was the inverse: the working tree held a required field that HEAD
did not, from another lane's uncommitted widening of a transcriber model — eight
occurrences in the working copy, zero at HEAD.

That attribution is worth preserving as method. A HEAD reproduction alone would
have pointed at this change; it took checking where the new field actually lived
to attribute it correctly.
