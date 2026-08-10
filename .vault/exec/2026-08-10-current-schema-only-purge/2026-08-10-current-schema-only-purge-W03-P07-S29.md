---
tags:
  - '#exec'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:00bd25b4cad06173b2a581436e412f3f870a6b7d518865b0ebb37a7e77f27567'
step_id: 'S29'
related:
  - "[[2026-08-10-current-schema-only-purge-plan]]"
---

# Stop an unreadable prior observation proving a first IVA period

## Scope

- `src/cadrumo/application/modelo/_iva_wallet_gate.py`
- `src/cadrumo/application/calculations/_iva_wallet_reconciliation.py`
- `src/cadrumo/application/modelo/tests/test_local_cross_period_carry.py`

## Description

- Report whether a prior-period Modelo 303 observation was stored alongside whether it could be used, so the caller can tell a genuine absence from evidence it failed to read.
- Reach the profile activity-start question only on a genuine absence.
- Correct two production comments that stated the defect as the guarantee.
- Add a real-adapter regression proving a stored-but-unreadable prior observation blocks.

## Outcome

Landed in `c2b79a1bc6`.

The defect was a laundering path, not a tolerance. A prior-period observation
this build could not interpret returned the same bare nothing as a period that
had genuinely never been filed. The caller paired that nothing with the
profile's activity-start proof and produced a non-blocking first-period zero, so
a taxpayer's carried credit became a zero on the compensacion with no refusal
and no signal.

The argument that scopes the fix is about the EXISTENCE of the stored
observation, not about why it turned out unusable: if one is persisted for the
prior period, the taxpayer had a prior period, which is the exact fact the
activity-start proof asserts did not exist. The artefact whose unreadability
triggers the zero is itself proof the zero is wrong. That holds identically for
the period or revision mismatch, the refused carry envelope, and the validated
envelope missing its available-compensation casilla, so all three now report the
observation as present and all three block.

The change is additive and its containment was measured before it was written:
the resolver has exactly one caller and the activity-start predicate exactly two,
all inside one module, so no shared signature moved and no consumer was swept.
The reconciliation function's parameters are untouched.

One assumption behind the routing turned out to be false and made the change
simpler rather than harder. The row was scoped on the belief that it would add a
refusal to a file whose every refusal a concurrent campaign is converting to a
structured precondition verdict. It adds no refusal at all -- it changes a
predicate and a return -- so the form question does not arise and the two
campaigns do not collide.

## Notes

The file carried 238 insertions and 69 deletions of another campaign's
uncommitted work with no reachable owner, so the change was landed through an
index-only drive against HEAD and then layered onto that working copy, which was
verified to still carry every line of the peer's work and none of it removed.
Without that second pass the peer's next working-tree commit would have reverted
this fix silently, with no conflict and a green result.

Two scope statements in this record's own row were wrong when written. The row
said the fix would cut one link and leave five open; the ruling widened it to the
three that share the argument, leaving the caller-distinguishability question --
which of the no-evidence outcomes a caller should be able to tell apart -- open as
its own row. The row also placed the peer's changed region outside the edit
region by a few lines; the resolver's tail had in fact been reformatted, which
surfaced only when a prepared patch refused to apply to the working copy.

Delivered narrower than the close conditions in one respect, stated rather than
absorbed: one regression covers the stored-but-unreadable path, and the existing
first-period test covers the genuine absence that must keep proving a zero. The
period-mismatch and missing-casilla paths return the same value through the same
statement and are not separately exercised.
